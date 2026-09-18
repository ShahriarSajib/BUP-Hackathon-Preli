import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    HOURS_PER_DAY = 24
    MAX_NOTES = 3
    MIN_NOTES = 1

    ENERGY_TOLERANCE = 0.01
    COST_TOLERANCE = 0.01
    ROUND_DECIMALS = 6

    OPTIMIZER_TIME_LIMIT_SECONDS = 5.0
    OPTIMIZER_SOLVER = "CBC"

    LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))
    LLM_PRIMARY_MAX_RETRIES = int(os.getenv("LLM_PRIMARY_MAX_RETRIES", "1"))
    LLM_FALLBACK_MAX_RETRIES = int(os.getenv("LLM_FALLBACK_MAX_RETRIES", "1"))

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_BASE_URL = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.GEMINI_API_KEY) or bool(self.GROQ_API_KEY)

    @property
    def groq_enabled(self) -> bool:
        return bool(self.GROQ_API_KEY)


settings = Settings()