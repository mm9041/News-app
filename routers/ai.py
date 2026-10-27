import json
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config import ai_conf
from config.db_conf import AsyncSessionLocal, get_database
from crud import ai_chat
from models.users import User
from schemas.ai import AiChatItemResponse, AiChatListResponse
from utils.auth import get_current_user
from utils.logger import get_logger
from utils.rate_limit import enforce
from utils.response import success_response

router = APIRouter(prefix="/api/ai", tags=["ai"])
logger = get_logger(__name__)

MAX_MESSAGE_CHARS = 8000
MAX_TOTAL_CHARS = 20000
MAX_MESSAGES = 50


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=MAX_MESSAGES)
    stream: bool = True
    # 默认用配置里的模型，也允许请求单独指定 —— 但必须在白名单内
    model: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def _check_total_length(self):
        """单条限长还不够：50 条 × 8000 字符仍能把一次请求撑到几十万字符。

        总预算卡在 2 万字符（约 1 万多 token），既覆盖正常多轮对话，
        又不至于让人拿一个账号把额度刷光。
        """
        total = sum(len(message.content) for message in self.messages)
        if total > MAX_TOTAL_CHARS:
            raise ValueError(f"对话内容过长（{total} 字符，上限 {MAX_TOTAL_CHARS}），请精简后重试")
        return self


def _resolve_model(requested: Optional[str]) -> str:
    if not requested:
        return ai_conf.AI_MODEL
    if requested not in ai_conf.allowed_models():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持模型 {requested}",
        )
    return requested


def _build_payload(req: ChatRequest) -> dict:
    return {
        "model": _resolve_model(req.model),
        "messages": [m.model_dump() for m in req.messages],
        "stream": req.stream,
    }


def _build_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ai_conf.AI_API_KEY}",
        # 阿里云 DashScope 走 SSE 需要这个头，其他兼容网关会忽略它
        "X-DashScope-SSE": "enable",
    }


def _extract_content(obj: dict) -> str:
    """从一个上游事件里取出文本增量。

    提取顺序**刻意与前端 AIChat.vue 保持一致** —— 换个顺序会导致落库的内容
    和用户屏幕上看到的对不上。兼容 OpenAI 格式与 DashScope 原生格式。
    """
    choices = obj.get("choices") or [{}]
    return (
        ((choices[0].get("delta") or {}).get("content"))
        or ((obj.get("output") or {}).get("text"))
        or ((choices[0].get("message") or {}).get("content"))
        or ""
    )


def _content_from_sse_line(line: str) -> str:
    """解析一行原始 SSE，取出其中的文本增量。"""
    if not line.startswith("data: "):
        return ""
    data = line[6:].strip()
    if not data or data == "[DONE]":
        return ""
    try:
        obj = json.loads(data)
    except ValueError:
        return ""
    if not isinstance(obj, dict) or obj.get("error"):
        return ""
    return _extract_content(obj)


def _last_user_message(req: ChatRequest) -> str:
    """取最后一条 user 消息，作为这一轮的提问落库。"""
    for msg in reversed(req.messages):
        if msg.role == "user":
            return msg.content
    return ""


async def _save_chat_record(user_id: int, message: str, response: str) -> None:
    """把一轮问答落库。

    这里**单独开一个短 session**，不复用请求级的 Depends(get_database)：
    流式回答是在 body 传输过程中才拼出完整文本的，那时请求级 session 早已随请求关闭。
    """
    try:
        async with AsyncSessionLocal() as db:
            await ai_chat.save_chat(db, user_id, message, response)
    except Exception as e:
        # 落库失败不能影响已经/正在返回给用户的回答
        logger.error("保存 AI 聊天记录失败：%s", e)


@router.post("/chat")
async def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    """把大模型请求代理到服务端，并把这一轮问答记到 ai_chat 表。

    - API Key 只存在于服务端 .env，前端只跟本接口说话（Key 不再进前端产物）。
    - 需要登录：`get_current_user` 从 Authorization 头校验 token，
      既是保护额度，也让聊天记录能挂到具体账号下（ai_chat.user_id 是 NOT NULL 外键）。

    流式：把上游 SSE 原样透传，同时在服务端把增量拼起来，结束后落库。
    非流式：聚合后按项目统一的 {code, message, data} 返回，并落库。
    """
    # 限流放在最前面：这里每成功一次都会真实产生上游费用
    await enforce(f"ai:{user.id}", 20, 60, "提问过于频繁，请 1 分钟后再试")

    # 先校验请求本身（模型白名单等），再检查服务有没有配好 ——
    # 请求本身不合法时应该报 400，而不是因为没配 Key 就先报 503
    payload = _build_payload(req)
    headers = _build_headers()
    user_message = _last_user_message(req)

    if not ai_conf.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="大模型未配置，请检查 .env 中的 AI_CHAT_URL 与 AI_API_KEY"
        )

    if not req.stream:
        async with httpx.AsyncClient(timeout=ai_conf.AI_TIMEOUT) as client:
            resp = await client.post(ai_conf.AI_CHAT_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"大模型返回 {resp.status_code}"
            )
        data = resp.json()
        content = _extract_content(data)
        if user_message and content:
            await _save_chat_record(user.id, user_message, content)
        return {"code": 200, "message": "success", "data": {"content": content}}

    async def event_stream():
        collected: List[str] = []
        try:
            async with httpx.AsyncClient(timeout=ai_conf.AI_TIMEOUT) as client:
                async with client.stream("POST", ai_conf.AI_CHAT_URL, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        # 上游失败时也要给前端一条 SSE，否则前端只会看到"无法生成回复"
                        yield f'data: {{"error": "upstream {resp.status_code}"}}\n\n'
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        yield f"{line}\n\n"
                        chunk = _content_from_sse_line(line)
                        if chunk:
                            collected.append(chunk)
        finally:
            # 兜底也写一次：用户中途关掉页面时，已经生成的部分照样存下来
            answer = "".join(collected)
            if user_message and answer:
                await _save_chat_record(user.id, user_message, answer)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 让 nginx 之类的反向代理不要缓冲 SSE
        }
    )


@router.get("/history")
async def get_history(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_database),
):
    """分页取当前用户的聊天记录，按时间倒序（最新的在前）。

    只返回**当前用户**的记录（`user.id` 来自 token），不提供按 user_id 查询的参数，
    否则就成了越权读别人对话的接口。
    """
    rows, total = await ai_chat.get_chat_list(db, user.id, page, page_size)
    has_more = total > page * page_size
    data = AiChatListResponse(
        list=[AiChatItemResponse.model_validate(row) for row in rows],
        total=total,
        has_more=has_more,
    )
    return success_response(data=data, message="获取聊天记录成功")
