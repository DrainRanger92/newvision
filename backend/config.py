from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8")

    bot_token: str = ""
    bot_enabled: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    db_path: str = "data/curtain_reader.db"
    fetch_timeout: float = 10.0
    fetch_max_bytes: int = 10_000_000
    deepseek_api_key: str = ""
    translation_model: str = "deepseek-chat"


settings = Settings()
