from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReviewMind API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = 10.0

    llm_api_key: str | None = None
    llm_api_base: str = "https://ai.sxuan.top/v1"
    llm_model_summary: str = "gpt-4o-mini"
    llm_model_review: str = "gpt-4o"
    llm_timeout_seconds: float = 30.0
    llm_mock_mode: bool = True

    # PostgreSQL 为默认数据库（含 pgvector 扩展），本地无 PG 时可通过
    # DATABASE_URL=sqlite+aiosqlite:///./reviewmind.db 切回 SQLite
    database_url: str = "postgresql+asyncpg://reviewmind:reviewmind@localhost:5432/reviewmind"
    redis_url: str = "redis://localhost:6379/0"

    # Embedding 配置（用于 pgvector 向量检索）
    embedding_api_key: str | None = None
    embedding_api_base: str = "https://ai.sxuan.top/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # RAG 分级触发阈值
    rag_light_min_files: int = 5
    rag_light_min_lines: int = 200
    rag_full_min_files: int = 15
    rag_full_min_lines: int = 1000
    # RAG 检索参数
    rag_top_k_light: int = 3
    rag_top_k_full: int = 5
    rag_max_snippet_chars: int = 2000
    rag_cache_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()