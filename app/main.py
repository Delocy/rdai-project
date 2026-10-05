import json
import logging
from contextlib import asynccontextmanager

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .agent.loop import run
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
    # first run against a fresh Qdrant (or one stopped part-way through): index
    # whatever of the sample catalogue is missing, so `docker compose up --build`
    # alone is enough to get real search results, with no separate ingest command
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
# turn oversized uploads away before they're read; the margin covers the form around the image
app.add_middleware(BodySizeLimit, limit=settings().max_upload_bytes + 64 * 1024)

# empty by default (same-origin dev/Docker); set when the frontend is deployed
# as a separate origin, e.g. a standalone Vercel project
if settings().cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up. /ready says whether it can actually serve searches."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness, for the compose healthcheck: Qdrant answers, the catalogue is indexed and
    both models are loaded."""
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
    """The model on its own: CLIP's 512-number unit vector for the text and/or the image,
    and their cosine similarity when both are given."""
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
    """Streams newline-delimited JSON: one {"type": "step", "step": Step} line
    per agent step as it happens, then a final {"type": "done", "response":
    SearchResponse} (or {"type": "error", "detail": str} if it crashes
    mid-stream, since headers are already sent by then)."""
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
            # the details stay in the server log - they can name internal hosts and paths
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
