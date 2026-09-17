import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from qdrant_client import models

from . import store
from .agent.loop import run
from .embeddings import embed_image
from .schemas import SearchResponse
from .security import read_image, require_api_key

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend" / "dist"
IMAGES = ROOT / "data" / "images"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.ensure_collection()
    yield


app = FastAPI(title="Visual Product Search", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse, dependencies=[Depends(require_api_key)])
async def search(
    query: str = Form(default=""),
    image: UploadFile | None = File(default=None),
) -> SearchResponse:
    if not query.strip() and image is None:
        raise HTTPException(status_code=400, detail="provide a query, an image, or both")
    data = await read_image(image) if image else None
    return run(query, data)


@app.post("/ingest", dependencies=[Depends(require_api_key)])
async def ingest(
    title: str = Form(...),
    price: float = Form(...),
    image: UploadFile = File(...),
    category: str | None = Form(default=None),
    colour: str | None = Form(default=None),
    image_url: str | None = Form(default=None),
) -> dict[str, str]:
    data = await read_image(image)
    point_id = str(uuid.uuid4())
    store.upsert(
        [
            models.PointStruct(
                id=point_id,
                vector=embed_image(data).tolist(),
                payload={
                    "title": title,
                    "price": price,
                    "category": category,
                    "colour": colour,
                    "image_url": image_url,
                },
            )
        ]
    )
    return {"id": point_id}


# mounted before the catch-all so /images wins over the frontend route
IMAGES.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES), name="images")

if FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="ui")
