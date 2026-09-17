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
    if rejected["over_price"] and constraints.price_max is not None:
        widened = constraints.price_max * 1.25
        return constraints.model_copy(update={"price_max": widened}), f"price ceiling -> {widened:.2f}"
    if rejected["wrong_colour"] and constraints.colour:
        return constraints.model_copy(update={"colour": None}), "dropped colour filter"
    if constraints.category:
        return constraints.model_copy(update={"category": None}), "widened category"
    return constraints, ""


def run(text: str, image_bytes: bytes | None) -> SearchResponse:
    constraints = parse_query(text)
    trace: list[Step] = []
    kept: list[Candidate] = []

    for iteration in range(1, settings().max_iterations + 1):
        vector = query_vector(text, image_bytes, constraints)
        points = store.search(vector, settings().top_k, constraints.price_max, constraints.category)

        if constraints.relative_cheaper and constraints.price_max is None and points:
            reference = float((points[0].payload or {}).get("price", 0.0))
            if reference:
                cap = reference * 0.8
                constraints = constraints.model_copy(
                    update={"price_max": cap, "relative_cheaper": False}
                )
                trace.append(
                    Step(
                        iteration=iteration,
                        action="derive budget",
                        detail=f"top match {reference:.2f}, cap {cap:.2f}",
                        kept=0,
                    )
                )
                points = store.search(vector, settings().top_k, cap, constraints.category)

        kept, rejected = apply(points, constraints)
        trace.append(
            Step(
                iteration=iteration,
                action="retrieve + check",
                detail=f"{len(points)} retrieved, rejected {rejected}",
                kept=len(kept),
            )
        )

        if len(kept) >= settings().shortlist:
            break

        constraints, note = repair(constraints, rejected)
        if not note:
            break
        trace.append(Step(iteration=iteration, action="repair", detail=note, kept=len(kept)))

    shortlist = kept[: settings().shortlist]
    ranked = justify(text or constraints.intent, shortlist, image_bytes)
    return SearchResponse(constraints=constraints, results=ranked, trace=trace)
