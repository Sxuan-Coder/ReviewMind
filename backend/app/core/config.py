from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReviewMind API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = 10.0

    llm_api_key: str | None = None
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model_summary: str = "gpt-4o-mini"
    llm_model_review: str = "gpt-4o"
    llm_timeout_seconds: float = 30.0
    llm_mock_mode: bool = True

    database_url: str = "sqlite+aiosqlite:///./reviewmind.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()