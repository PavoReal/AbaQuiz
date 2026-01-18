"""
Configuration management for AbaQuiz.

Loads settings from:
1. Environment variables (.env file) - secrets
2. config/config.json - application settings

Supports ${ENV_VAR} substitution in JSON values.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class Settings:
    """Application settings loaded from environment and config file."""

    def __init__(self) -> None:
        # Load .env file
        load_dotenv()

        # Load config.json
        self._config = self._load_config()

        # Required environment variables
        self.telegram_bot_token = self._require_env("TELEGRAM_BOT_TOKEN")
        self.anthropic_api_key = self._require_env("ANTHROPIC_API_KEY")

        # Optional environment variables with defaults
        self.database_path = os.getenv("DATABASE_PATH", "./data/abaquiz.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Bot settings from config
        bot_config = self._config.get("bot", {})
        self.default_timezone = bot_config.get(
            "default_timezone", "America/Los_Angeles"
        )
        self.morning_quiz_hour = bot_config.get("morning_quiz_hour", 8)
        self.evening_quiz_hour = bot_config.get("evening_quiz_hour", 20)

        # Admin settings
        admin_config = self._config.get("admin", {})
        self.admin_users: list[int] = admin_config.get("admin_users", [])
        self.summary_time = admin_config.get("summary_time", "09:00")
        self.default_summary_enabled = admin_config.get(
            "default_summary_enabled", True
        )
        self.default_alerts_enabled = admin_config.get(
            "default_alerts_enabled", True
        )

        # Rate limiting
        rate_config = self._config.get("rate_limit", {})
        self.extra_questions_per_day = rate_config.get(
            "extra_questions_per_day", 5
        )
        self.requests_per_minute = rate_config.get("requests_per_minute", 10)

        # Question generation
        gen_config = self._config.get("question_generation", {})
        self.pool_threshold_per_area = gen_config.get(
            "pool_threshold_per_area", 20
        )
        self.batch_size = gen_config.get("batch_size", 10)
        self.type_distribution = gen_config.get(
            "type_distribution",
            {"multiple_choice": 0.8, "true_false": 0.2},
        )
        self.claude_model = gen_config.get("model", "claude-sonnet-4-20250514")

        # Question selection
        sel_config = self._config.get("question_selection", {})
        self.weak_area_ratio = sel_config.get("weak_area_ratio", 0.2)
        self.min_answers_for_weak_calc = sel_config.get(
            "min_answers_for_weak_calc", 5
        )
        self.focus_preference_weight = sel_config.get(
            "focus_preference_weight", 2.0
        )

        # Error handling
        err_config = self._config.get("error_handling", {})
        self.max_retries = err_config.get("max_retries", 3)
        self.retry_delays = err_config.get("retry_delays", [0, 5, 15])

        # Messages
        self.rejection_messages: list[str] = self._config.get(
            "rejection_messages", []
        )

        # Pricing
        self.pricing = self._config.get("pricing", {})

    def _require_env(self, name: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(name)
        if not value:
            raise ValueError(
                f"Required environment variable {name} is not set. "
                f"Please set it in your .env file."
            )
        return value

    def _load_config(self) -> dict[str, Any]:
        """Load config.json with environment variable substitution."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"

        if not config_path.exists():
            return {}

        with open(config_path) as f:
            content = f.read()

        # Substitute ${ENV_VAR} patterns
        def replace_env_var(match: re.Match) -> str:
            var_name = match.group(1)
            return os.getenv(var_name, "")

        content = re.sub(r"\$\{(\w+)\}", replace_env_var, content)

        return json.loads(content)

    def is_admin(self, telegram_id: int) -> bool:
        """Check if a user is an admin."""
        return telegram_id in self.admin_users

    def get_model_pricing(self, model: str) -> dict[str, float] | None:
        """Get pricing info for a model."""
        return self.pricing.get("anthropic", {}).get(model)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
