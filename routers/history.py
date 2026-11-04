from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_conf import get_database
from crud import history
from crud.news_cache import news_exists
from models.users import User
from schemas.history import HistoryAddRequest, HistoryNewsItemResponse, HistoryListResponse
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/history", tags=["history"])


@router.post("/add")
async def add_history(data: HistoryAddRequest,
                      user: User = Depends(get_current_user),
                      db: AsyncSession = Depends(get_database)):
    """
    添加历史记录
    """
    # 先判存在，避免靠外键报错兜底（那样会变成 400「关联数据不存在」，语义不对）
    if not await news_exists(db, data.news_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="新闻不存在")

    result = await history.add_history(db, user.id, data.news_id)
    return success_response(message="添加成功", data=result)


@router.get("/list")
async def get_history_list(page: int = Query(1, ge=1),
                           page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
                           user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_database)):
    """
    获取历史记录列表
    """
    rows, total = await history.get_history_list(db, user.id, page, page_size)

    has_more = total > page * page_size

    # 显式挑字段，不要 `{**news.__dict__}`：那会把 _sa_instance_state
    # 这类 ORM 内部状态一起带进去，靠 Pydantic 忽略私有键才没出事。
    history_list = [
        HistoryNewsItemResponse(
            id=news.id,
            title=news.title,
            description=news.description,
            image=news.image,
            author=news.author,
            category_id=news.category_id,
            views=news.views,
            publish_time=news.publish_time,
            history_id=history_id,
            view_time=view_time,
        )
        for news, view_time, history_id in rows
    ]

    data = HistoryListResponse(list=history_list, total=total, hasMore=has_more)

    return success_response(data=data)


@router.delete("/delete/{news_id}")
async def delete_history(news_id: int,
                         user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_database)):
    """删除某条新闻的浏览历史。

    ⚠️ 路径参数是**新闻 id**，不是 history 表的主键 —— 前端 `History.vue`
    传的是 `item.id`（列表项里的新闻 id）。以前这个参数叫 `history_id`，
    名字和行为不符，容易让人照着名字改成 `History.id` 从而误删别人的记录。
    """
    result = await history.delete_history(db, user.id, news_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="历史记录不存在")
    return success_response(message="删除成功")


@router.delete("/clear")
async def clear_history(user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_database)):
    """
    清空历史记录
    """
    await history.clear_history(db, user.id)
    return success_response(message="清空成功")
