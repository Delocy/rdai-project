import re

from qdrant_client import models

from ..schemas import Candidate, Constraints


# everyday words for things the catalogue labels differently (keys are singular)
SYNONYMS = {
    "sneaker": "shoe",
    "trainer": "shoe",
    "footwear": "shoe",
    "running": "sport",
    "jogging": "sport",
    "tee": "tshirt",
    "purse": "handbag",
    "wristwatch": "watch",
    "shade": "sunglass",
    "fragrance": "perfume",
    "gray": "grey",
}


def _singular(word: str) -> str:
    if word.endswith(("ches", "shes", "sses", "xes")):  # watches, dresses, boxes
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def words(text: str) -> list[str]:
    """Normalised words in order: lower case, singular, hyphens dropped, synonyms applied."""
    normalised = (_singular(word) for word in re.findall(r"[a-z0-9]+", re.sub(r"[-']", "", text.lower())))
    return [SYNONYMS.get(word, word) for word in normalised]


def loosely_matches(wanted: str, actual: str | None) -> bool:
    """Whole words, either way round, ignoring case, hyphens and plurals: "blue" fits
    "Navy Blue", "t-shirt" fits "Tshirts" - but "Shirts" doesn't fit "Tshirts", which a
    plain substring test would let through."""
    if not actual:
        return False
    want, have = set(words(wanted)), set(words(actual))
    return bool(want) and bool(have) and (want <= have or have <= want)


def demote(constraints: Constraints, field: str, value: str) -> Constraints:
    """Drop a hard filter but keep its meaning as a soft signal in the embedding probe."""
    intent = constraints.intent
    if value.strip().lower() not in intent.lower():
        intent = f"{value.strip()} {intent}".strip()
    return constraints.model_copy(update={field: None, "intent": intent})


def misses(candidate: Candidate, requested: Constraints) -> list[str]:
    """How a result falls short of what was asked for, so relaxed matches are labelled as such."""
    out = []
    if requested.price_max is not None and candidate.price > requested.price_max:
        out.append(f"over budget by {candidate.price - requested.price_max:.2f}")
    if requested.colour and not loosely_matches(requested.colour, candidate.colour):
        out.append(f"{candidate.colour or 'unknown colour'}, not {requested.colour}")
    if requested.category and not loosely_matches(requested.category, candidate.category):
        out.append(f"{candidate.category or 'uncategorised'}, not {requested.category}")
    return out


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
