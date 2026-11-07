import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 项目根目录（config/ 的上一级），.env 就放在那里
BASE_DIR = Path(__file__).resolve().parent.parent
# override=False：已存在的真实环境变量优先，.env 只做兜底
load_dotenv(BASE_DIR / ".env", override=False)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "news_app")


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# 用 async 引擎必须带异步驱动：mysql+aiomysql://
# 写成 mysql:// 或 mysql+pymysql:// 会报 "The asyncio extension requires an async driver"
ASYNC_DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=_env_bool("DB_ECHO", False),  # 输出 SQL 日志，默认关闭（开启后参数也会被打进日志）
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),  # 设置连接池活跃的连接数
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),  # 允许额外的连接数
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 控制事务提交后，session 里已加载对象的属性是否被标记为“过期”，异步环境下必须关掉
)


async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()  # 回滚操作
            # 必须 re-raise：否则路由抛的 HTTPException 会被吃掉，
            # FastAPI 会误报 "Response not awaited..."
            raise
        finally:
            await session.close()
