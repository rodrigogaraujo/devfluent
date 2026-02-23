from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str

    # AI Services
    OPENAI_API_KEY: str
    GROQ_API_KEY: str

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = ""

    # Cloudflare R2 (optional)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY: str = ""
    R2_SECRET_KEY: str = ""
    R2_BUCKET: str = "devfluent-audio"
    R2_PUBLIC_URL: str = ""

    # Monitoring
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""

    # Admin
    ADMIN_TELEGRAM_ID: str = ""

    # Tuning
    MAX_CONTEXT_TOKENS: int = 4000
    CONVERSATION_TIMEOUT_MIN: int = 30
    MAX_MESSAGES_PER_DAY: int = 100
    TTS_SPEED: float = 1.0


settings = Settings()
