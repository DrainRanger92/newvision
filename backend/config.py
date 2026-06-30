"""
# @module: config
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8")

    bot_token: str = ""
    bot_enabled: bool = False
    webapp_url: str = ""
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "https://newvision-*.run.app",
    ]
    db_path: str = "data/curtain_reader.db"
    fetch_timeout: float = 10.0
    fetch_max_bytes: int = 10_000_000
    deepseek_api_key: str = ""
    translation_model: str = "deepseek-chat"

    # Webhook mode (for Cloud Run)
    bot_mode: str = "polling"  # "polling" | "webhook"
    webhook_url: str = ""
    webhook_path: str = "/webhook/telegram"
    webhook_secret: str = ""

    # Static files
    serve_static: bool = False
    static_dir: str = "frontend/dist"

    @property
    def mini_app_url(self) -> str:
        return self.webapp_url or "http://localhost:5173"

    @property
    def effective_webhook_url(self) -> str:
        return self.webhook_url or self.webapp_url


settings = Settings()
