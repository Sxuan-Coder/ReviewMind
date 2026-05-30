"""测试全局 fixtures：为每个测试重置数据库。"""

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
async def _reset_db():
    """每个测试前清空数据库表，保证测试隔离。"""
    from app.core.database import engine, init_db
    from app.models.db_models import Base

    # 重建表（drop all + create all）
    async with engine.begin() as conn:
        # 仅 PostgreSQL 需要注册 pgvector 扩展
        if "postgresql" in settings.database_url:
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield