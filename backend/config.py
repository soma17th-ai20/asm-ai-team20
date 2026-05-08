from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    similarity_threshold: float = 0.55
    llm_threshold: int = 7
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_MODEL: str = "gpt-4o"
    REDIS_HOST: str
    REDIS_PORT: str

    model_config = {"env_file": ".env"}


settings = Settings()