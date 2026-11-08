"""图片上传。

安全上有三处必须做的，缺一不可：
1. **不信文件名和 Content-Type** —— 两者都由客户端随便填，改后缀就能传 .php。
   这里读文件头魔数判断真实类型，扩展名也由魔数决定，不用用户给的名字。
2. **限制大小** —— 否则一个 2GB 的文件直接把内存和磁盘吃满。
3. **文件名自己生成** —— 用 uuid，杜绝 `../../etc/passwd` 这类路径穿越。

存储放在项目根的 `uploads/YYYY/MM/` 下，由 main.py 挂到 `/uploads` 静态目录。
换成对象存储时只要改这个文件。
"""

import uuid
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from models.users import User
from schemas.common import ApiResponse
from utils.api_docs import AUTHENTICATED_ERRORS
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/upload", tags=["upload"])


class UploadImageResponse(BaseModel):
    url: str


UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
MAX_SIZE = 5 * 1024 * 1024  # 5MB

# 魔数 -> 扩展名。顺序无关，但 PNG/GIF 的前缀不能和 JPEG 混淆
_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
)


def _detect_ext(head: bytes) -> str | None:
    for signature, ext in _SIGNATURES:
        if head.startswith(signature):
            return ext
    # WebP: RIFF....WEBP
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


@router.post(
    "/image",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[UploadImageResponse],
    responses=AUTHENTICATED_ERRORS,
)
async def upload_image(
    request: Request,
    file: UploadFile = File(..., description="图片文件"),
    user: User = Depends(get_current_user),
):
    """登录用户都能上传（管理员发新闻、普通用户换头像）。"""
    data = await file.read()

    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="文件为空")
    if len(data) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="图片不能超过 5MB",
        )

    ext = _detect_ext(data[:16])
    if not ext:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="只支持 JPG / PNG / GIF / WebP",
        )

    now = datetime.now()
    rel_dir = f"{now:%Y/%m}"
    target_dir = UPLOAD_ROOT / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    # 落盘放线程池：write_bytes 是同步阻塞调用，最大 5MB 的写盘会把事件循环卡住，
    # 同时进来的其他请求（包括 SSE 流）都会被拖慢。anyio 是 starlette 自带的依赖，
    # 不用额外装 aiofiles。
    await anyio.to_thread.run_sync((target_dir / filename).write_bytes, data)

    # 返回完整 URL，和库里已有的图片字段（picsum 的完整 URL）保持一致，
    # 前端拿到直接塞进 <img> 即可。
    url = f"/uploads/{rel_dir}/{filename}"
    absolute_url = str(request.base_url).rstrip("/") + url
    return success_response(
        data=UploadImageResponse(url=absolute_url),
        message="上传成功",
        status_code=status.HTTP_201_CREATED,
        headers={"Location": absolute_url},
    )
