import csv
import uuid
from pathlib import Path

from qdrant_client import models

from . import store
from .embeddings import embed_image_paths


def rows(catalogue: Path):
    with catalogue.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            missing = [f for f in ("title", "price", "image") if not row.get(f)]
            if missing:
                continue
            yield row


def point_id(row: dict) -> str:
    """Stable per image file, so re-indexing overwrites a product instead of duplicating it."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"catalogue/{row['image']}"))


def seed_from_csv(catalogue: Path, images: Path, batch_size: int = 32, log=print) -> int:
    """(Re-)index every row; products already in the collection are overwritten in place."""
    return _index(_indexable(catalogue, images), images, batch_size, log)


def seed_missing(catalogue: Path, images: Path, batch_size: int = 32, log=print) -> int:
    """Index the rows that aren't in the collection yet, so an interrupted first start
    resumes. A collection filled some other way (older random ids) is left alone."""
    pending = _indexable(catalogue, images)
    existing = store.existing_ids([point_id(row) for row in pending])
    if not existing and store.count() > 0:
        return 0
    missing = [row for row in pending if point_id(row) not in existing]
    return _index(missing, images, batch_size, log)


def _indexable(catalogue: Path, images: Path) -> list[dict]:
    return [row for row in rows(catalogue) if (images / row["image"]).is_file()]


def _index(pending: list[dict], images: Path, batch_size: int, log) -> int:
    total = 0
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        vectors = embed_image_paths([str(images / row["image"]) for row in batch])
        store.upsert(
            [
                models.PointStruct(id=point_id(row), vector=vector.tolist(), payload=_payload(row))
                for row, vector in zip(batch, vectors)
            ]
        )
        total += len(batch)
        log(f"indexed {total}")
    return total


def _payload(row: dict) -> dict:
    return {
        "title": row["title"],
        "price": float(row["price"]),
        "category": row.get("category") or None,
        "colour": row.get("colour") or None,
        "image_url": row.get("image_url") or f"/images/{row['image']}",
    }
