from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MCP
    SILPO_MCP_URL: str = "https://mcp.silpo.ua/mcp"
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/auth/silpo/callback"
    OAUTH_CLIENT_NAME: str = "foresight-hackathon-agent"

    # LLM
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # Weather
    OPEN_METEO_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"

    # Infra
    DATABASE_URL: str = "postgresql+asyncpg://foresight:foresight@localhost:5432/foresight"
    REDIS_URL: str = "redis://localhost:6379/0"
    TOKEN_ENCRYPTION_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"

    # Engine thresholds
    MIN_CONFIDENCE: float = 0.62
    MAX_SUGGESTIONS: int = 3
    PRICE_CAP_RATIO: float = 0.12
    MIN_PURCHASES_FOR_CYCLE: int = 3
    SHRINKAGE_K: float = 8
    SHOCK_DELTA_APPARENT: float = 7.0
    SHOCK_Z_SCORE: float = 1.8
    DEBOUNCE_SECONDS: int = 20
    DISMISS_BAN_DAYS: int = 90

    # Final score weights (SPEC §7.3)
    SCORE_A: float = 1.0
    SCORE_B: float = 0.6
    SCORE_C: float = 0.25
    SCORE_D: float = 0.15

    # Demo
    DEMO_MODE: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
