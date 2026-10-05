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
    # price filters need this index (Qdrant Cloud rejects unindexed filters); safe to repeat
    client().create_payload_index(
        collection_name=name,
        field_name="price",
        field_schema=models.PayloadSchemaType.FLOAT,
    )
    # keyword indexes for facet_values() and the category and colour filters
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
    """Every distinct value of a keyword field, e.g. all categories."""
    hits = client().facet(collection_name=settings().collection, key=key, limit=1000).hits
    return sorted(str(hit.value) for hit in hits)


def _filter(
    price_max: float | None, categories: list[str] | None, colours: list[str] | None
) -> models.Filter | None:
    """None skips a field; a list matches any of its labels."""
    must: list[models.Condition] = []
    if price_max is not None:
        must.append(models.FieldCondition(key="price", range=models.Range(lte=price_max)))
    for key, labels in (("category", categories), ("colour", colours)):
        if labels is not None:
            must.append(models.FieldCondition(key=key, match=models.MatchAny(any=labels)))
    return models.Filter(must=must) if must else None


def search(
    vector: np.ndarray,
    limit: int,
    price_max: float | None = None,
    categories: list[str] | None = None,
    colours: list[str] | None = None,
) -> list[models.ScoredPoint]:
    """The nearest products that pass every filter."""
    if categories == [] or colours == []:
        return []  # a label the catalogue doesn't have
    return client().query_points(
        collection_name=settings().collection,
        query=vector.tolist(),
        limit=limit,
        query_filter=_filter(price_max, categories, colours),
        with_payload=True,
        with_vectors=False,
    ).points


def count_matching(
    price_max: float | None = None,
    categories: list[str] | None = None,
    colours: list[str] | None = None,
) -> int:
    """How many products pass these filters."""
    if categories == [] or colours == []:
        return 0
    return client().count(
        collection_name=settings().collection,
        count_filter=_filter(price_max, categories, colours),
        exact=True,
    ).count
