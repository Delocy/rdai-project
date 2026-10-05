from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "change-me"
    # searches and embeds per client per minute, 0 for no limit
    rate_limit_per_minute: int = 30
    max_upload_bytes: int = 5 * 1024 * 1024

    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    collection: str = "products"

    max_iterations: int = 3
    top_k: int = 24
    shortlist: int = 5



def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
