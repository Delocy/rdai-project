from collections.abc import Iterator

import numpy as np

from .. import store
from ..config import settings
from ..embeddings import embed_image, embed_text
from ..llm import TEXT, VISION, configured
from ..schemas import Candidate, Constraints, SearchResponse, Step
from .checks import apply, demote, misses
from .justify import justify
from .parse import parse_query, read_rules


def query_vector(text: str, image_bytes: bytes | None, constraints: Constraints) -> np.ndarray:
    vectors = []
    if image_bytes:
        vectors.append(embed_image(image_bytes))
    # "like this but cheaper" with a photo: search on the photo, not the comparison words
    probe = constraints.intent or ("" if image_bytes else text)
    if probe.strip():
        vectors.append(embed_text(probe))
    if not vectors:
        raise ValueError("need an image or a text query")

    combined = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(combined))
    return combined / norm if norm else combined


def repair(constraints: Constraints, rejected: dict[str, int]) -> tuple[Constraints, str]:
    """Relax the least important constraint first: colour, then budget, then category."""
    if rejected["wrong_colour"] and constraints.colour:
        return demote(constraints, "colour", constraints.colour), "colour filter -> query text"
    if constraints.price_max is not None:
        widened = constraints.price_max * 1.25
        return constraints.model_copy(update={"price_max": widened}), f"price ceiling -> {widened:.2f}"
    if rejected["wrong_category"] and constraints.category:
        return demote(constraints, "category", constraints.category), "category filter -> query text"
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
    return ", ".join(parts) or "no filters - similarity only"


def run(text: str, image_bytes: bytes | None) -> Iterator[Step | SearchResponse]:
    """Runs the search agent, yielding each Step as it happens and finishing
    with the complete SearchResponse, so callers can show live progress."""
    trace: list[Step] = []
    kept: list[Candidate] = []
    degraded = False

    def emit(**fields) -> Step:
        step = Step(**fields)
        trace.append(step)
        return step

    # rules read the request unless LLM parsing is switched on and a model is set up;
    # a model that fails falls back to the rules rather than to no filters at all
    constraints, parser = read_rules(text), "rules"
    if settings().llm_parse and text.strip() and configured(TEXT):
        try:
            constraints, parser = parse_query(text), "llm"
        except RuntimeError as exc:
            degraded = True
            yield emit(
                iteration=0,
                action="parse unavailable",
                detail=f"{str(exc)[:120]} - read with rules instead",
                kept=0,
            )
    yield emit(iteration=0, action=f"read request ({parser})", detail=_describe(constraints), kept=0)
    # repairs relax `constraints`; `requested` keeps what was actually asked for
    requested = constraints

    for iteration in range(1, settings().max_iterations + 1):
        try:
            vector = query_vector(text, image_bytes, constraints)
        except Exception as exc:
            if not image_bytes:
                raise
            # the vision + text CLIP models together can exceed hosts with a
            # small /tmp (e.g. Vercel's 500MB cap) - fall back to text only
            # rather than failing the whole search
            image_bytes = None
            degraded = True
            yield emit(
                iteration=iteration,
                action="image embedding unavailable",
                detail=str(exc)[:160],
                kept=0,
            )
            vector = query_vector(text, image_bytes, constraints)
        points = store.search(vector, settings().top_k, constraints.price_max)

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
                points = store.search(vector, settings().top_k, cap)

        kept, rejected = apply(points, constraints)
        yield emit(
            iteration=iteration,
            action="retrieve + check",
            detail=f"{len(points)} retrieved, rejected {rejected}",
            kept=len(kept),
        )

        if len(kept) >= settings().shortlist or iteration == settings().max_iterations:
            break

        constraints, note = repair(constraints, rejected)
        if not note:
            break
        yield emit(iteration=iteration, action="repair", detail=note, kept=len(kept))

    # CLIP similarity order unless a vision model is set up to look at the photos
    shortlist = kept[: settings().shortlist]
    ranked, ranker = shortlist, "similarity"
    explained_empty = False
    if configured(VISION):
        try:
            ranked, ranker = justify(text or constraints.intent, shortlist, image_bytes), "llm"
        except RuntimeError as exc:
            degraded = True
            yield emit(
                iteration=0,
                action="ranking unavailable",
                detail=f"{str(exc)[:120]} - kept similarity order",
                kept=len(shortlist),
            )
        else:
            dropped = len(shortlist) - len(ranked)
            if dropped:
                explained_empty = True
                yield emit(
                    iteration=0,
                    action="dropped weak matches",
                    detail=f"{dropped} nearest neighbour(s) didn't actually match the request",
                    kept=len(ranked),
                )

    if not ranked and not explained_empty:
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
        parser=parser,
        ranker=ranker,
        degraded=degraded,
    )
