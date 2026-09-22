from collections.abc import Iterator

import numpy as np

from .. import store
from ..config import settings
from ..embeddings import embed_image, embed_text
from ..schemas import Candidate, Constraints, SearchResponse, Step
from .checks import apply
from .justify import justify
from .parse import parse_query


def query_vector(text: str, image_bytes: bytes | None, constraints: Constraints) -> np.ndarray:
    vectors = []
    if image_bytes:
        vectors.append(embed_image(image_bytes))
    probe = constraints.intent or text
    if probe.strip():
        vectors.append(embed_text(probe))
    if not vectors:
        raise ValueError("need an image or a text query")

    combined = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(combined))
    return combined / norm if norm else combined


def repair(constraints: Constraints, rejected: dict[str, int]) -> tuple[Constraints, str]:
    for field in ("colour", "category"):
        value = getattr(constraints, field)
        if rejected[f"wrong_{field}"] and value:
            return _demote(constraints, field, value), f"{field} filter -> query text"

    if constraints.price_max is not None:
        widened = constraints.price_max * 1.25
        return constraints.model_copy(update={"price_max": widened}), f"price ceiling -> {widened:.2f}"
    return constraints, ""


def _demote(constraints: Constraints, field: str, value: str) -> Constraints:
    """Drop a hard filter but keep its meaning as a soft signal in the embedding probe."""
    intent = constraints.intent
    if value.strip().lower() not in intent.lower():
        intent = f"{value.strip()} {intent}".strip()
    return constraints.model_copy(update={field: None, "intent": intent})


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

    try:
        constraints = parse_query(text)
    except RuntimeError as exc:
        constraints = Constraints(intent=text)
        degraded = True
        yield emit(iteration=0, action="parse unavailable", detail=str(exc)[:160], kept=0)

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

    shortlist = kept[: settings().shortlist]
    try:
        ranked = justify(text or constraints.intent, shortlist, image_bytes)
    except RuntimeError as exc:
        ranked = shortlist
        degraded = True
        yield emit(
            iteration=0, action="ranking unavailable", detail=str(exc)[:160], kept=len(shortlist)
        )

    yield SearchResponse(constraints=constraints, results=ranked, trace=trace, degraded=degraded)
