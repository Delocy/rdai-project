import csv
import uuid
from pathlib import Path

from qdrant_client import models

from . import store
from .embeddings import embed_image_path


def rows(catalogue: Path):
    with catalogue.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            missing = [f for f in ("title", "price", "image") if not row.get(f)]
            if missing:
                continue
            yield row


def seed_from_csv(catalogue: Path, images: Path, batch_size: int = 32, log=print) -> int:
    batch: list[models.PointStruct] = []
    total = 0

    for row in rows(catalogue):
        path = images / row["image"]
        if not path.is_file():
            continue
        batch.append(
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embed_image_path(str(path)).tolist(),
                payload={
                    "title": row["title"],
                    "price": float(row["price"]),
                    "category": row.get("category") or None,
                    "colour": row.get("colour") or None,
                    "image_url": row.get("image_url") or f"/images/{row['image']}",
                },
            )
        )
        if len(batch) >= batch_size:
            store.upsert(batch)
            total += len(batch)
            log(f"indexed {total}")
            batch = []

    if batch:
        store.upsert(batch)
        total += len(batch)
    return total
