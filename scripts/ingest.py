import argparse
import csv
import uuid
from pathlib import Path

from qdrant_client import models

from app import store
from app.embeddings import embed_image_path

FIELDS = ("title", "price", "image", "category", "colour")


def rows(catalogue: Path):
    with catalogue.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            missing = [f for f in ("title", "price", "image") if not row.get(f)]
            if missing:
                continue
            yield row


def main() -> None:
    parser = argparse.ArgumentParser(description="index a CSV catalogue into Qdrant")
    parser.add_argument("catalogue", type=Path)
    parser.add_argument("--images", type=Path, default=Path("data/images"))
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    store.ensure_collection()
    batch: list[models.PointStruct] = []
    total = 0

    for row in rows(args.catalogue):
        path = args.images / row["image"]
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
        if len(batch) >= args.batch:
            store.upsert(batch)
            total += len(batch)
            print(f"indexed {total}")
            batch = []

    if batch:
        store.upsert(batch)
        total += len(batch)
    print(f"done, {total} items")


if __name__ == "__main__":
    main()
