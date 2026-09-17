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


def embed_image(data: bytes) -> np.ndarray:
    image = Image.open(BytesIO(data)).convert("RGB")
    return _unit(next(iter(_images().embed([image]))))


def embed_image_path(path: str) -> np.ndarray:
    return _unit(next(iter(_images().embed([path]))))


def embed_text(text: str) -> np.ndarray:
    return _unit(next(iter(_texts().embed([text]))))


def _unit(vector) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    return array / norm if norm else array
