"""Configuration loading for the diagnosis agent."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://agent_user:agent_pass@127.0.0.1:5432/diagnosis_db",
    )
    READING_FRESHNESS_SECONDS = int(os.getenv("READING_FRESHNESS_SECONDS", "300"))
    TEST_MODE = os.getenv("AGENT_TEST_MODE", "").lower() in ("1", "true", "yes")

    @staticmethod
    def has_provider_key() -> bool:
        return bool(
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("AZURE_API_KEY")
        )


config = Config()

