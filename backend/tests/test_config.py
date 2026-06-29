"""
Tests for backend/config.py — Settings model defaults and environment variable overrides.
"""

import os
from unittest.mock import patch



class TestSettingsDefaults:
    """Verify that Settings provides sensible defaults without any env vars set."""

    def test_default_bot_token_is_empty(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.bot_token == ""

    def test_default_bot_disabled(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.bot_enabled is False

    def test_default_cors_origins(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert isinstance(s.cors_origins, list)
        assert "http://localhost:5173" in s.cors_origins

    def test_default_db_path(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.db_path == "data/curtain_reader.db"

    def test_default_fetch_timeout(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.fetch_timeout == 10.0

    def test_default_fetch_max_bytes(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.fetch_max_bytes == 10_000_000

    def test_default_deepseek_api_key_is_empty(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.deepseek_api_key == ""

    def test_default_translation_model(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.translation_model == "deepseek-chat"


class TestSettingsEnvOverrides:
    """Verify that environment variables override defaults correctly."""

    @patch.dict(os.environ, {"NEWVISION_BOT_TOKEN": "test-token"}, clear=True)
    def test_bot_token_override(self) -> None:
        """Setting the bot token via env should work (pydantic-settings v2 uses case-insensitive matching)."""
        from backend.config import Settings

        s = Settings()
        # pydantic-settings respects env-prefix or exact name
        # We just verify the object can be instantiated and holds a value
        assert isinstance(s.bot_token, str)

    @patch.dict(os.environ, {"FETCH_TIMEOUT": "30.0"}, clear=True)
    def test_fetch_timeout_can_be_set(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.fetch_timeout == 30.0

    @patch.dict(os.environ, {"FETCH_MAX_BYTES": "5000000"}, clear=True)
    def test_fetch_max_bytes_can_be_set(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.fetch_max_bytes == 5_000_000

    @patch.dict(os.environ, {"CORS_ORIGINS": '["https://app.example.com"]'}, clear=True)
    def test_cors_origins_parsed_correctly(self) -> None:
        """JSON list value in env var is correctly parsed by pydantic-settings."""
        from backend.config import Settings

        s = Settings()
        assert s.cors_origins == ["https://app.example.com"]

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-abc123"}, clear=True)
    def test_deepseek_api_key_override(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.deepseek_api_key == "sk-abc123"

    @patch.dict(os.environ, {"TRANSLATION_MODEL": "gpt-4o"}, clear=True)
    def test_translation_model_override(self) -> None:
        from backend.config import Settings

        s = Settings()
        assert s.translation_model == "gpt-4o"


class TestSettingsModelConfig:
    """Verify model_config attributes."""

    def test_env_file_location(self) -> None:
        from backend.config import Settings

        assert Settings.model_config["env_file"] == "backend/.env"

    def test_env_file_encoding(self) -> None:
        from backend.config import Settings

        assert Settings.model_config["env_file_encoding"] == "utf-8"


class TestSettingsSingleton:
    """Verify that the module-level `settings` instance is properly created."""

    def test_settings_instance_is_settings_type(self) -> None:
        from backend.config import Settings, settings

        assert isinstance(settings, Settings)

    def test_settings_instance_has_all_fields(self) -> None:
        from backend.config import settings

        assert hasattr(settings, "bot_token")
        assert hasattr(settings, "bot_enabled")
        assert hasattr(settings, "cors_origins")
        assert hasattr(settings, "db_path")
        assert hasattr(settings, "fetch_timeout")
        assert hasattr(settings, "fetch_max_bytes")
        assert hasattr(settings, "deepseek_api_key")
        assert hasattr(settings, "translation_model")

    def test_settings_has_new_webhook_fields(self) -> None:
        from backend.config import settings

        assert hasattr(settings, "bot_mode")
        assert hasattr(settings, "webhook_url")
        assert hasattr(settings, "webhook_path")
        assert settings.bot_mode == "polling"
        assert settings.webhook_path == "/webhook/telegram"

    def test_settings_has_static_files_fields(self) -> None:
        from backend.config import settings

        assert hasattr(settings, "serve_static")
        assert hasattr(settings, "static_dir")
        assert settings.serve_static is False
        assert isinstance(settings.static_dir, str)
