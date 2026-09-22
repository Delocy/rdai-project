import argparse
import csv
import json
import random
import urllib.request
from pathlib import Path

DATASET = "ashraq/fashion-product-images-small"
ROWS_URL = (
    "https://datasets-server.huggingface.co/rows"
    f"?dataset={DATASET}&config=default&split=train&offset={{offset}}&length={{length}}"
)
PAGE = 100

# the source dataset ships no prices, so they are invented per article type
BASE_PRICES = {
    "Tshirts": 18, "Shirts": 35, "Jeans": 45, "Tops": 25, "Kurtas": 30,
    "Casual Shoes": 55, "Sports Shoes": 70, "Formal Shoes": 80, "Heels": 60,
    "Sandals": 35, "Flip Flops": 12, "Watches": 120, "Sunglasses": 85,
    "Handbags": 65, "Backpacks": 40, "Belts": 22, "Wallets": 30,
}
DEFAULT_PRICE = 40


def price_for(article_type: str, seed: int) -> float:
    base = BASE_PRICES.get(article_type, DEFAULT_PRICE)
    return round(base * random.Random(seed).uniform(0.6, 1.8), 2)


def fetch_rows(limit: int):
    collected = 0
    while collected < limit:
        length = min(PAGE, limit - collected)
        url = ROWS_URL.format(offset=collected, length=length)
        with urllib.request.urlopen(url, timeout=60) as response:
            rows = json.load(response).get("rows", [])
        if not rows:
            return
        for entry in rows:
            yield entry["row"]
        collected += len(rows)


DEFAULT_IMAGE_BASE_URL = "https://raw.githubusercontent.com/Delocy/rdai-project/main/data/images"


def main() -> None:
    parser = argparse.ArgumentParser(description="download a sample catalogue")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument(
        "--image-base-url",
        default=DEFAULT_IMAGE_BASE_URL,
        help=(
            "base URL the downloaded images will be reachable at once committed "
            "(e.g. a raw.githubusercontent.com path) - the dataset's own hosted "
            "URLs are signed and expire within ~a day, so they're not usable as "
            "a lasting image_url. Pass '' to fall back to the (short-lived) "
            "source URL instead."
        ),
    )
    args = parser.parse_args()

    images = args.out / "images"
    images.mkdir(parents=True, exist_ok=True)
    catalogue = args.out / "catalogue.csv"

    written = 0
    with catalogue.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["title", "price", "image", "category", "colour", "image_url"]
        )
        writer.writeheader()

        for row in fetch_rows(args.limit):
            title = row.get("productDisplayName")
            source = (row.get("image") or {}).get("src")
            if not title or not source:
                continue

            name = f"{row['id']}.jpg"
            target = images / name
            if not target.exists():
                try:
                    urllib.request.urlretrieve(source, target)
                except Exception:
                    continue

            image_url = f"{args.image_base_url}/{name}" if args.image_base_url else source
            writer.writerow({
                "title": title,
                "price": price_for(row.get("articleType", ""), row["id"]),
                "image": name,
                "category": row.get("articleType") or row.get("subCategory"),
                "colour": row.get("baseColour"),
                "image_url": image_url,
            })
            written += 1
            if written % 50 == 0:
                print(f"fetched {written}")

    print(f"done, {written} items -> {catalogue}")


if __name__ == "__main__":
    main()
