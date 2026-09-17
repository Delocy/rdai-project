import base64
from functools import lru_cache
from typing import Any

from openai import OpenAI

from .config import settings


@lru_cache
def _client() -> OpenAI:
    cfg = settings()
    return OpenAI(api_key=cfg.openrouter_api_key, base_url=cfg.openrouter_base_url)


def complete(messages: list[dict[str, Any]], models: list[str], json_mode: bool = False) -> str:
    kwargs: dict[str, Any] = {"messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last: Exception | None = None
    for model in models:
        try:
            response = _client().chat.completions.create(model=model, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last = exc
    raise RuntimeError(f"all models failed, last error: {last}")


def image_part(data: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    encoded = base64.b64encode(data).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
