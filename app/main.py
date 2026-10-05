import json
import logging
from contextlib import asynccontextmanager

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .search.loop import run
from .config import settings
from .embeddings import VECTOR_SIZE, embed_image, embed_text, warm_up
from .embeddings import loaded as models_loaded
from .paths import CATALOGUE, FRONTEND, IMAGES
from .schemas import Embedding, Step
from .security import BodySizeLimit, rate_limit, read_image, require_api_key
from .seed import seed_missing

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.ensure_collection()
    # index whatever of the sample catalogue is missing, so `docker compose up` alone works
    if CATALOGUE.is_file():
        try:
            total = seed_missing(CATALOGUE, IMAGES)
            if total:
                print(f"seeded {total} catalogue items")
        except Exception as exc:
            print(f"catalogue auto-seed failed, starting without it: {exc}")
    warm_up()
    yield


app = FastAPI(title="Visual Product Search", lifespan=lifespan)
# reject oversized uploads before reading them; the margin covers the rest of the form
app.add_middleware(BodySizeLimit, limit=settings().max_upload_bytes + 64 * 1024)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness for the compose healthcheck: Qdrant is up, the catalogue is indexed and
    the models are loaded."""
    try:
        products = store.count()
    except Exception:
        return _not_ready("vector database unreachable")
    if not products:
        return _not_ready("catalogue not indexed yet")
    if not models_loaded():
        return _not_ready("models still loading")
    return JSONResponse({"status": "ready", "products": products})


def _not_ready(reason: str) -> JSONResponse:
    return JSONResponse({"status": "not ready", "reason": reason}, status_code=503)


@app.post("/embed", dependencies=[Depends(require_api_key), Depends(rate_limit)])
async def embed(
    text: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> Embedding:
    """CLIP vectors for the text and/or image, and their cosine similarity when both are given."""
    if not text.strip() and image is None:
        raise HTTPException(status_code=400, detail="provide text, an image, or both")
    data = await read_image(image) if image else None
    text_vector = await run_in_threadpool(embed_text, text) if text.strip() else None
    image_vector = await run_in_threadpool(embed_image, data) if data else None
    both = text_vector is not None and image_vector is not None
    return Embedding(
        model="clip-ViT-B-32",
        dimensions=VECTOR_SIZE,
        text=None if text_vector is None else text_vector.tolist(),
        image=None if image_vector is None else image_vector.tolist(),
        similarity=float(np.dot(text_vector, image_vector)) if both else None,
    )


@app.post("/search", dependencies=[Depends(require_api_key), Depends(rate_limit)])
async def search(
    query: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> StreamingResponse:
    """Streams one JSON line per search step, then a "done" line with the results, or an
    "error" line if it fails partway."""
    if not query.strip() and image is None:
        raise HTTPException(status_code=400, detail="provide a query, an image, or both")
    data = await read_image(image) if image else None

    def events():
        try:
            for item in run(query, data):
                if isinstance(item, Step):
                    yield json.dumps({"type": "step", "step": item.model_dump()}) + "\n"
                else:
                    yield json.dumps({"type": "done", "response": item.model_dump()}) + "\n"
        except Exception:
            # details stay in the server log, since they can name internal hosts and paths
            log.exception("search failed")
            yield json.dumps({"type": "error", "detail": "search failed - see the server log"}) + "\n"

    return StreamingResponse(events(), media_type="application/x-ndjson")


try:
    IMAGES.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
else:
    app.mount("/images", StaticFiles(directory=IMAGES), name="images")

if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="ui")
