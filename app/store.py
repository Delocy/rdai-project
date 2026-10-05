from functools import lru_cache

import numpy as np
from qdrant_client import QdrantClient, models

from .config import settings
from .embeddings import VECTOR_SIZE


@lru_cache
def client() -> QdrantClient:
    return QdrantClient(url=settings().qdrant_url, api_key=settings().qdrant_api_key or None)


def ensure_collection() -> None:
    name = settings().collection
    if not client().collection_exists(name):
        client().create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
        )
    # search() filters on price; Qdrant (at least on Cloud) rejects a filter on
    # an unindexed field with 400 Bad Request, so this must exist before any
    # price_max-constrained search runs. Idempotent - safe on every startup.
    client().create_payload_index(
        collection_name=name,
        field_name="price",
        field_schema=models.PayloadSchemaType.FLOAT,
    )
    # keyword indexes let facet_values() list the catalogue's own labels for the parser
    for field in ("category", "colour"):
        client().create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )


def upsert(points: list[models.PointStruct]) -> None:
    client().upsert(collection_name=settings().collection, points=points)


def count() -> int:
    return client().count(settings().collection, exact=False).count


def existing_ids(ids: list[str]) -> set[str]:
    if not ids:
        return set()
    found = client().retrieve(
        collection_name=settings().collection, ids=ids, with_payload=False, with_vectors=False
    )
    return {str(point.id) for point in found}


def facet_values(key: str) -> list[str]:
    """Every distinct value of a keyword-indexed payload field, e.g. all catalogue categories."""
    hits = client().facet(collection_name=settings().collection, key=key, limit=1000).hits
    return sorted(str(hit.value) for hit in hits)


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
        with_vectors=False,
    ).points
