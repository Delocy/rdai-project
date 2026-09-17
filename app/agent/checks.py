import numpy as np
from qdrant_client import models

from ..config import settings
from ..embeddings import embed_text
from ..schemas import Candidate, Constraints


def apply(
    points: list[models.ScoredPoint], constraints: Constraints
) -> tuple[list[Candidate], dict[str, int]]:
    target = embed_text(f"a photo of a {constraints.colour} item") if constraints.colour else None
    kept: list[Candidate] = []
    rejected = {"over_price": 0, "wrong_colour": 0}

    for point in points:
        payload = point.payload or {}
        price = float(payload.get("price", 0.0))

        if constraints.price_max is not None and price > constraints.price_max:
            rejected["over_price"] += 1
            continue

        colour_score = None
        if target is not None:
            colour_score = float(np.dot(target, np.asarray(point.vector, dtype=np.float32)))
            # CLIP cosine sits low in absolute terms; ~0.22 separates match from mismatch here
            if colour_score < settings().colour_threshold:
                rejected["wrong_colour"] += 1
                continue

        kept.append(
            Candidate(
                id=str(point.id),
                title=payload.get("title", ""),
                price=price,
                category=payload.get("category"),
                colour=payload.get("colour"),
                image_url=payload.get("image_url"),
                score=float(point.score),
                colour_score=colour_score,
            )
        )

    return kept, rejected
