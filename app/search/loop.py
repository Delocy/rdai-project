from collections.abc import Callable, Iterator

import numpy as np

from .. import store
from ..config import settings
from ..embeddings import embed_image, embed_text
from ..schemas import Candidate, Constraints, SearchResponse, Step
from .checks import apply, demote, loosely_matches, misses
from .parse import catalogue_vocabulary, read_rules

Vocabulary = tuple[list[str], list[str]]


def query_vector(text: str, image_bytes: bytes | None, constraints: Constraints) -> np.ndarray:
    vectors = []
    if image_bytes:
        vectors.append(embed_image(image_bytes))
    # with a photo, search on the photo rather than words like "cheaper"
    probe = constraints.intent or ("" if image_bytes else text)
    if probe.strip():
        vectors.append(embed_text(probe))
    if not vectors:
        raise ValueError("need an image or a text query")

    combined = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(combined))
    return combined / norm if norm else combined


def filters(constraints: Constraints, vocabulary: Vocabulary) -> dict:
    """Qdrant filters for the constraints. A category or colour becomes every catalogue label
    it names, so "shoes" covers Casual, Sports and Formal Shoes."""

    def labels(value: str | None, known: list[str]) -> list[str] | None:
        if not value or not known:
            return None
        return [label for label in known if loosely_matches(value, label)]

    categories, colours = vocabulary
    return {
        "price_max": constraints.price_max,
        "categories": labels(constraints.category, categories),
        "colours": labels(constraints.colour, colours),
    }


def repair(
    constraints: Constraints, matching: Callable[[Constraints], int]
) -> tuple[Constraints, str]:
    """Relax one constraint, in the order colour, budget, category. Colour and category are
    only dropped when that brings in more products."""
    current = matching(constraints)
    if constraints.colour:
        relaxed = demote(constraints, "colour", constraints.colour)
        if matching(relaxed) > current:
            return relaxed, "colour filter -> query text"
    if constraints.price_max is not None:
        widened = constraints.price_max * 1.25
        return constraints.model_copy(update={"price_max": widened}), f"price ceiling -> {widened:.2f}"
    if constraints.category:
        relaxed = demote(constraints, "category", constraints.category)
        if matching(relaxed) > current:
            return relaxed, "category filter -> query text"
    return constraints, ""


def _describe(constraints: Constraints) -> str:
    parts = []
    if constraints.category:
        parts.append(f"category {constraints.category}")
    if constraints.colour:
        parts.append(f"colour {constraints.colour}")
    if constraints.price_max is not None:
        parts.append(f"under {constraints.price_max:.2f}")
    if constraints.relative_cheaper:
        parts.append("cheaper than the closest match")
    return ", ".join(parts) or "no filters"


def run(text: str, image_bytes: bytes | None) -> Iterator[Step | SearchResponse]:
    """Yields each Step as it happens, then the SearchResponse."""
    trace: list[Step] = []
    kept: list[Candidate] = []

    def emit(**fields) -> Step:
        step = Step(**fields)
        trace.append(step)
        return step

    vocabulary = catalogue_vocabulary()
    constraints = read_rules(text, vocabulary)

    def matching(c: Constraints) -> int:
        return store.count_matching(**filters(c, vocabulary))

    yield emit(iteration=0, action="read request", detail=_describe(constraints), kept=0)
    # repairs relax `constraints`, `requested` keeps what was asked for
    requested = constraints

    for iteration in range(1, settings().max_iterations + 1):
        vector = query_vector(text, image_bytes, constraints)
        points = store.search(vector, settings().top_k, **filters(constraints, vocabulary))

        if constraints.relative_cheaper and constraints.price_max is None and points:
            reference = float((points[0].payload or {}).get("price", 0.0))
            if reference:
                cap = reference * 0.8
                constraints = constraints.model_copy(
                    update={"price_max": cap, "relative_cheaper": False}
                )
                requested = requested.model_copy(update={"price_max": cap})
                yield emit(
                    iteration=iteration,
                    action="derive budget",
                    detail=f"top match {reference:.2f}, cap {cap:.2f}",
                    kept=0,
                )
                points = store.search(vector, settings().top_k, **filters(constraints, vocabulary))

        # Qdrant already filtered; apply() turns the points into results
        kept, _ = apply(points, constraints)
        yield emit(
            iteration=iteration,
            action="retrieve + check",
            detail=f"{matching(constraints)} matching products in the catalogue",
            kept=len(kept),
        )

        if len(kept) >= settings().shortlist or iteration == settings().max_iterations:
            break

        constraints, note = repair(constraints, matching)
        if not note:
            break
        yield emit(iteration=iteration, action="repair", detail=note, kept=len(kept))

    # Qdrant returns the nearest first, so this is already in CLIP similarity order
    ranked = kept[: settings().shortlist]
    if not ranked:
        yield emit(
            iteration=0,
            action="no match",
            detail="nothing in the catalogue fit this request",
            kept=0,
        )

    for candidate in ranked:
        candidate.misses = misses(candidate, requested)

    yield SearchResponse(
        requested=requested,
        constraints=constraints,
        results=ranked,
        trace=trace,
    )
