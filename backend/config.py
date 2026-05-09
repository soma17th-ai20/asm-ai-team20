from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    similarity_threshold: float = 0.55
    llm_threshold: int = 7
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o"
    REDIS_HOST: str
    REDIS_PORT: str

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/asm"

    CRAWLER_API_URL: str = "http://localhost:8000"
    CRAWL_INTERVAL_MINUTES: int = 30

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    DEV_RECIPIENT_EMAIL: str = ""

    DAILY_LIMIT_PER_USER: int = 5

    model_config = {"env_file": ".env"}


settings = Settings()