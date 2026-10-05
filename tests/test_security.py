from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.security import BodySizeLimit


def client_with_limit(limit: int) -> tuple[TestClient, list[int]]:
    """An app that reads the whole body, behind the limit; returns the sizes it managed to read."""
    reads = []

    async def endpoint(request):
        body = await request.body()
        reads.append(len(body))
        return PlainTextResponse("read")

    app = Starlette(routes=[Route("/", endpoint, methods=["POST"])])
    app.add_middleware(BodySizeLimit, limit=limit)  # mounted the way app/main.py mounts it
    return TestClient(app), reads


def test_a_body_over_the_limit_is_refused_before_the_app_reads_it():
    client, reads = client_with_limit(100)
    assert client.post("/", content=b"x" * 101).status_code == 413
    assert reads == []


def test_a_body_within_the_limit_goes_through():
    client, reads = client_with_limit(100)
    assert client.post("/", content=b"x" * 100).status_code == 200
    assert reads == [100]


def test_a_streamed_body_with_no_declared_length_is_cut_off_at_the_limit():
    client, reads = client_with_limit(100)

    def chunks():
        for _ in range(10):
            yield b"x" * 50

    assert client.post("/", content=chunks()).status_code == 413
    assert reads == []
