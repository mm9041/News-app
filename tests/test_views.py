"""阅读量增量逻辑。

只测纯内存部分：Redis 用 AsyncMock 替换，不碰数据库、也不依赖真实 Redis。
核心不变量是「返回给用户的 views = 库内值 + 未回写增量」，
而且增量只能叠加一次（缓存里存的是库内原值）。
"""

import asyncio
from unittest.mock import AsyncMock, patch

from crud import news_views
from schemas.base import NewsItemBase


def _item(news_id: int = 1, views: int = 10) -> NewsItemBase:
    return NewsItemBase(
        id=news_id,
        title="标题",
        description=None,
        image=None,
        author=None,
        category_id=1,
        views=views,
        publish_time=None,
    )


def test_apply_view_deltas_adds_pending_increment():
    items = [_item(1, 10), _item(2, 20)]
    with patch.object(news_views.view_counter, "get_deltas", new=AsyncMock(return_value={1: 3})):
        result = asyncio.run(news_views.apply_view_deltas(items))

    assert result[0].views == 13
    assert result[1].views == 20  # 没有增量的保持原值


def test_apply_view_deltas_when_redis_unavailable():
    items = [_item(1, 10)]
    with patch.object(news_views.view_counter, "get_deltas", new=AsyncMock(return_value={})):
        result = asyncio.run(news_views.apply_view_deltas(items))

    assert result[0].views == 10


def test_apply_view_deltas_empty_list():
    assert asyncio.run(news_views.apply_view_deltas([])) == []


def test_display_views_is_db_plus_delta():
    with patch.object(news_views.view_counter, "get_deltas", new=AsyncMock(return_value={7: 2})):
        assert asyncio.run(news_views.get_display_views(7, 100)) == 102


def test_display_views_without_delta():
    with patch.object(news_views.view_counter, "get_deltas", new=AsyncMock(return_value={})):
        assert asyncio.run(news_views.get_display_views(7, 100)) == 100
