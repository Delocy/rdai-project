import json
import secrets
import time
from collections import defaultdict, deque
from io import BytesIO

from fastapi import Header, HTTPException, Request, UploadFile
from PIL import Image

from .config import settings

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
# a 5 MB PNG of one flat colour can claim a 100-megapixel canvas; refuse anything bigger
# than this before decoding it
MAX_IMAGE_PIXELS = 25_000_000


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_api_key, settings().api_key):
        raise HTTPException(status_code=401, detail="invalid api key")


_requests: dict[str, deque] = defaultdict(deque)  # client -> times of its recent requests


def rate_limit(request: Request) -> None:
    """Each search runs CLIP on the CPU (and maybe an LLM call), so an unthrottled loop of
    requests would pin the CPU or burn the free tier's daily quota."""
    allowed = settings().rate_limit_per_minute
    if allowed <= 0:
        return
    now = time.monotonic()
    recent = _requests[request.client.host if request.client else "unknown"]
    while recent and now - recent[0] >= 60:
        recent.popleft()
    if len(recent) >= allowed:
        retry = int(60 - (now - recent[0])) + 1
        raise HTTPException(status_code=429, detail="too many requests", headers={"Retry-After": str(retry)})
    recent.append(now)


async def read_image(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="unsupported image type")
    limit = settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="image too large")
    # Content-Type is whatever the client claims - check the bytes themselves
    try:
        with Image.open(BytesIO(data)) as image:
            detected, (width, height) = image.format, image.size
            image.verify()
    except Exception:
        raise HTTPException(status_code=415, detail="not a readable image") from None
    if detected not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(status_code=415, detail="unsupported image type")
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=413, detail="image dimensions too large")
    return data


class _BodyTooLarge(Exception):
    pass


class BodySizeLimit:
    """Turns away request bodies over `limit` bytes before anything reads them. Starlette parses
    a whole multipart upload (spilling it to disk) before an endpoint can check its size."""

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and int(declared) > self.limit:
            return await self._refuse(send)

        received, started = 0, False

        async def counted_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.limit:  # a chunked body that never declared its length
                raise _BodyTooLarge
            return message

        async def tracked_send(message):
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, counted_receive, tracked_send)
        except _BodyTooLarge:
            if not started:
                await self._refuse(send)

    @staticmethod
    async def _refuse(send) -> None:
        body = json.dumps({"detail": "request body too large"}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
        await send({"type": "http.response.start", "status": 413, "headers": headers})
        await send({"type": "http.response.body", "body": body})
