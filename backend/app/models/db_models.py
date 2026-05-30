"""数据库 ORM 模型。"""

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ReviewJobModel(Base):
    """ReviewJob 持久化模型，所有结构化数据用 JSON 文本存储。"""

    __tablename__ = "review_jobs"

    job_id = Column(String(64), primary_key=True)
    pr_url = Column(String(512), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # 结构化数据以 JSON 文本存储（兼容 SQLite 和 PostgreSQL）
    pr_info = Column(Text, nullable=True)           # JSON 字符串
    progress_events = Column(Text, nullable=True)    # JSON 数组字符串
    pipeline_result = Column(Text, nullable=True)    # JSON 字符串
    report = Column(Text, nullable=True)             # ReviewReport JSON