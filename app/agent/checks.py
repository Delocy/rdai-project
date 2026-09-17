from qdrant_client import models

from ..schemas import Candidate, Constraints


def loosely_matches(wanted: str, actual: str | None) -> bool:
    """Substring match either way; model output rarely matches catalogue casing exactly."""
    if not actual:
        return False
    wanted, actual = wanted.strip().lower(), actual.strip().lower()
    return wanted in actual or actual in wanted


def apply(
    points: list[models.ScoredPoint], constraints: Constraints
) -> tuple[list[Candidate], dict[str, int]]:
    kept: list[Candidate] = []
    rejected = {"wrong_colour": 0, "wrong_category": 0}

    for point in points:
        payload = point.payload or {}
        price = float(payload.get("price", 0.0))

        # price is filtered server side; colour and category need loose matching
        if constraints.colour and not loosely_matches(constraints.colour, payload.get("colour")):
            rejected["wrong_colour"] += 1
            continue

        if constraints.category and not loosely_matches(
            constraints.category, payload.get("category")
        ):
            rejected["wrong_category"] += 1
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
            )
        )

    return kept, rejected
