from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    similarity_threshold: float = 0.55
    llm_threshold: int = 7
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"

    # PostgreSQL — docker-compose의 기본값과 같다. 운영에서는 .env로 덮어쓴다.
    database_url: str = "postgresql+psycopg2://team20:team20pw@localhost:5432/team20"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
