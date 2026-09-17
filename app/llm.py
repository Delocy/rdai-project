import base64
from functools import lru_cache
from typing import Any

from openai import OpenAI

from .config import settings

TEXT = "text"
VISION = "vision"


@lru_cache
def _openrouter() -> OpenAI:
    cfg = settings()
    return OpenAI(api_key=cfg.openrouter_api_key, base_url=cfg.openrouter_base_url)


@lru_cache
def _ollama() -> OpenAI:
    # ollama ignores the key but the client requires one
    return OpenAI(api_key="ollama", base_url=settings().ollama_url.rstrip("/") + "/v1")


def _attempts(kind: str) -> list[tuple[OpenAI, str]]:
    cfg = settings()
    remote = cfg.text_model_list if kind == TEXT else cfg.vision_model_list
    local = cfg.ollama_text_model if kind == TEXT else cfg.ollama_vision_model

    chain = [(_openrouter(), model) for model in remote] if cfg.openrouter_api_key else []
    if local:
        chain.append((_ollama(), local))
    return chain


def complete(messages: list[dict[str, Any]], kind: str, json_mode: bool = False) -> str:
    kwargs: dict[str, Any] = {"messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last: Exception | None = None
    for client, model in _attempts(kind):
        try:
            response = client.chat.completions.create(model=model, **kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last = exc

    raise RuntimeError(f"no {kind} model available, last error: {last}")


def image_part(data: bytes, mime: str = "image/jpeg") -> dict[str, Any]:
    encoded = base64.b64encode(data).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
