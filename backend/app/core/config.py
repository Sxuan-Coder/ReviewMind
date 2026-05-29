from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReviewMind API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()