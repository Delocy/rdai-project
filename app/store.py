from functools import lru_cache

import numpy as np
from qdrant_client import QdrantClient, models

from .config import settings
from .embeddings import VECTOR_SIZE


@lru_cache
def client() -> QdrantClient:
    return QdrantClient(url=settings().qdrant_url)


def ensure_collection() -> None:
    name = settings().collection
    if client().collection_exists(name):
        return
    client().create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )


def upsert(points: list[models.PointStruct]) -> None:
    client().upsert(collection_name=settings().collection, points=points)


def search(
    vector: np.ndarray,
    limit: int,
    price_max: float | None = None,
) -> list[models.ScoredPoint]:
    must: list[models.Condition] = []
    if price_max is not None:
        must.append(models.FieldCondition(key="price", range=models.Range(lte=price_max)))

    return client().query_points(
        collection_name=settings().collection,
        query=vector.tolist(),
        limit=limit,
        query_filter=models.Filter(must=must) if must else None,
        with_payload=True,
        with_vectors=True,
    ).points
