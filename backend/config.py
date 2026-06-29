"""
# @module: config
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8")

    bot_token: str = ""
    bot_enabled: bool = False
    mini_app_url: str = "http://localhost:5173"
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

    # Static files
    serve_static: bool = False
    static_dir: str = "frontend/dist"


settings = Settings()
