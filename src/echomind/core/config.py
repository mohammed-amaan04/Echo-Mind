from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EchoMind API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/echomind"
    async_database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/echomind"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "openai/gpt-oss-20b"
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    embedding_model: str = "all-MiniLM-L6-v2"
    spacy_model: str = "en_core_web_trf"
    ollama_model: str = "mistral"
    echomind_phase2_fallback: bool = True
    echomind_ollama_required: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
