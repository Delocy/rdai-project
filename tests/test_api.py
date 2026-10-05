import io
import json
from collections import defaultdict, deque

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main, security
from app.config import settings
from app.schemas import Constraints, SearchResponse, Step

# no context manager, so startup (Qdrant, seeding) never runs
client = TestClient(main.app)


def key() -> dict:
    return {"X-API-Key": settings().api_key}


def image_bytes(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format=fmt)
    return buffer.getvalue()


def events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def upload(name: str, data: bytes, content_type: str):
    return client.post("/search", data={"query": ""}, files={"image": (name, data, content_type)}, headers=key())


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    """A fresh rate-limit window per test, and no limit unless a test sets one."""
    monkeypatch.setattr(security, "_requests", defaultdict(deque))
    monkeypatch.setattr(settings(), "rate_limit_per_minute", 0)


@pytest.fixture
def search_loop(monkeypatch) -> list:
    """Replaces the search loop with a scripted one and records what it was called with."""
    calls = []

    def scripted(text, image):
        calls.append((text, image))
        yield Step(iteration=1, action="retrieve + check", detail="", kept=0)
        yield SearchResponse(constraints=Constraints(intent=text), results=[])

    monkeypatch.setattr(main, "run", scripted)
    return calls


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_search_needs_the_api_key(search_loop):
    assert client.post("/search", data={"query": "blue shirt"}).status_code == 401
    wrong = {"X-API-Key": "wrong"}
    assert client.post("/search", data={"query": "blue shirt"}, headers=wrong).status_code == 401
    assert search_loop == []


def test_search_needs_a_query_or_an_image(search_loop):
    assert client.post("/search", data={"query": "  "}, headers=key()).status_code == 400


def test_search_streams_each_step_then_the_result(search_loop):
    response = client.post("/search", data={"query": "blue shirt"}, headers=key())
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert [event["type"] for event in events(response)] == ["step", "done"]


def test_crash_hides_internal_details(monkeypatch):
    def crashing(text, image):
        yield Step(iteration=1, action="retrieve + check", detail="", kept=0)
        raise RuntimeError("connection to qdrant:6333 refused")

    monkeypatch.setattr(main, "run", crashing)
    response = client.post("/search", data={"query": "blue shirt"}, headers=key())
    assert [event["type"] for event in events(response)] == ["step", "error"]
    assert "qdrant" not in events(response)[-1]["detail"]


def test_an_uploaded_photo_reaches_the_search(search_loop):
    photo = image_bytes("PNG")
    assert upload("x.png", photo, "image/png").status_code == 200
    assert search_loop == [("", photo)]


def test_an_unsupported_content_type_is_rejected(search_loop):
    assert upload("x.gif", image_bytes("GIF"), "image/gif").status_code == 415


def test_rejects_non_image_bytes(search_loop):
    assert upload("x.jpg", b"not an image", "image/jpeg").status_code == 415
    assert search_loop == []


def test_rejects_unsupported_format(search_loop):
    assert upload("x.png", image_bytes("GIF"), "image/png").status_code == 415
    assert search_loop == []


def test_an_oversized_upload_is_rejected(search_loop, monkeypatch):
    monkeypatch.setattr(settings(), "max_upload_bytes", 10)
    assert upload("x.png", image_bytes("PNG"), "image/png").status_code == 413


def test_rejects_too_many_pixels(search_loop, monkeypatch):
    monkeypatch.setattr(security, "MAX_IMAGE_PIXELS", 10)  # the test image is 4x4
    assert upload("x.png", image_bytes("PNG"), "image/png").status_code == 413
    assert search_loop == []


def search_status() -> int:
    return client.post("/search", data={"query": "shirt"}, headers=key()).status_code


def test_rate_limit(search_loop, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_per_minute", 2)
    assert [search_status() for _ in range(3)] == [200, 200, 429]


def test_a_turned_away_search_says_when_to_retry(search_loop, monkeypatch):
    monkeypatch.setattr(settings(), "rate_limit_per_minute", 1)
    search_status()
    response = client.post("/search", data={"query": "shirt"}, headers=key())
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_the_http_api_is_read_only():
    # the catalogue only changes from inside the container (scripts/ingest.py)
    assert set(client.get("/openapi.json").json()["paths"]) == {"/health", "/ready", "/embed", "/search"}
    assert client.post("/ingest", headers=key()).status_code in (404, 405)


def unit_vector(axis: int) -> np.ndarray:
    vector = np.zeros(512, dtype=np.float32)
    vector[axis] = 1.0
    return vector


def test_embed_returns_the_clip_vector_for_text(monkeypatch):
    monkeypatch.setattr(main, "embed_text", lambda text: unit_vector(0))
    body = client.post("/embed", data={"text": "red shoe"}, headers=key()).json()
    assert body["dimensions"] == 512
    assert len(body["text"]) == 512
    assert body["image"] is None
    assert body["similarity"] is None


def test_embed_compares_text_with_an_image(monkeypatch):
    monkeypatch.setattr(main, "embed_text", lambda text: unit_vector(0))
    monkeypatch.setattr(main, "embed_image", lambda data: unit_vector(0))
    response = client.post(
        "/embed",
        data={"text": "red shoe"},
        files={"image": ("x.png", image_bytes("PNG"), "image/png")},
        headers=key(),
    )
    assert response.json()["similarity"] == pytest.approx(1.0)


def test_embed_needs_text_or_an_image():
    assert client.post("/embed", data={"text": " "}, headers=key()).status_code == 400


def test_embed_needs_the_api_key():
    assert client.post("/embed", data={"text": "red shoe"}).status_code == 401


def test_ready(monkeypatch):
    monkeypatch.setattr(main.store, "count", lambda: 300)
    monkeypatch.setattr(main, "models_loaded", lambda: True)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["products"] == 300


@pytest.mark.parametrize("products, loaded", [(None, True), (0, True), (300, False)])
def test_not_ready(monkeypatch, products, loaded):
    def count():
        if products is None:
            raise ConnectionError("qdrant unreachable")
        return products

    monkeypatch.setattr(main.store, "count", count)
    monkeypatch.setattr(main, "models_loaded", lambda: loaded)
    assert client.get("/ready").status_code == 503
