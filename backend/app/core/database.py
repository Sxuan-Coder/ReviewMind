"""SQLAlchemy 异步数据库引擎与会话工厂。

默认使用 PostgreSQL + pgvector，通过 DATABASE_URL 配置可切换 SQLite。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """获取数据库会话（可用于 FastAPI Depends 或手动调用）。"""
    async with async_session() as session:
        yield session  # type: ignore[misc]


async def init_db() -> None:
    """启动时注册 pgvector 扩展并建表。"""
    from app.models.db_models import Base  # noqa: F811

    async with engine.begin() as conn:
        # 仅 PostgreSQL 需要注册 pgvector 扩展
        if "postgresql" in settings.database_url:
            await conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
        await conn.run_sync(Base.metadata.create_all)