from functools import lru_cache
from io import BytesIO

import numpy as np
from fastembed import ImageEmbedding, TextEmbedding
from PIL import Image

VISION_MODEL = "Qdrant/clip-ViT-B-32-vision"
TEXT_MODEL = "Qdrant/clip-ViT-B-32-text"
VECTOR_SIZE = 512


@lru_cache
def _images() -> ImageEmbedding:
    return ImageEmbedding(VISION_MODEL)


@lru_cache
def _texts() -> TextEmbedding:
    return TextEmbedding(TEXT_MODEL)


def warm_up() -> None:
    """Load both models at startup so the first search doesn't wait. A failed load is
    retried on first use."""
    for load in (_texts, _images):
        try:
            load()
        except Exception as exc:
            print(f"model warm-up failed, will retry on first use: {exc}")


def loaded() -> bool:
    return bool(_texts.cache_info().currsize and _images.cache_info().currsize)


def embed_image(data: bytes) -> np.ndarray:
    image = Image.open(BytesIO(data)).convert("RGB")
    return _unit(next(iter(_images().embed([image]))))


def embed_image_paths(paths: list[str]) -> list[np.ndarray]:
    # one ONNX run per batch, about twice as fast as one image at a time
    return [_unit(vector) for vector in _images().embed(paths, batch_size=max(len(paths), 1))]


def embed_text(text: str) -> np.ndarray:
    return _unit(next(iter(_texts().embed([text]))))


def _unit(vector) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    return array / norm if norm else array
