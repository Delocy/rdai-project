from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    text_models: str = "meta-llama/llama-3.3-70b-instruct:free"
    vision_models: str = "qwen/qwen2.5-vl-72b-instruct:free"

    api_key: str = "change-me"
    max_upload_bytes: int = 5 * 1024 * 1024

    qdrant_url: str = "http://qdrant:6333"
    collection: str = "products"

    max_iterations: int = 3
    top_k: int = 24
    shortlist: int = 5
    colour_threshold: float = 0.22

    @property
    def text_model_list(self) -> list[str]:
        return _split(self.text_models)

    @property
    def vision_model_list(self) -> list[str]:
        return _split(self.vision_models)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
