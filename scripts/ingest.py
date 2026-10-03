import argparse
from pathlib import Path

from app import store
from app.seed import seed_from_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="index a CSV catalogue into Qdrant")
    parser.add_argument("catalogue", type=Path)
    parser.add_argument("--images", type=Path, default=Path("data/images"))
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()

    store.ensure_collection()
    total = seed_from_csv(args.catalogue, args.images, args.batch)
    print(f"done, {total} items")


if __name__ == "__main__":
    main()
