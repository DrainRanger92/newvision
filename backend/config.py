"""
<MODULE_CONTRACT>
name: config
layer: Data
depends: []
responsibility: Application configuration from environment variables and .env file
contract: Provides a singleton `settings` object with typed, validated configuration valid at import time
</MODULE_CONTRACT>

<LINKS>
- main: uses settings to configure app, CORS, DB path, API keys
- bot: reads bot_token and bot_enabled to control polling
- parser: reads fetch_timeout and fetch_max_bytes
- translator: reads deepseek_api_key and translation_model
</LINKS>
"""

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
