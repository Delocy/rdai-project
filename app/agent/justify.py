import json
from typing import Any

from ..llm import VISION, complete, image_part
from ..schemas import Candidate

SYSTEM = (
    "You rank shopping search results. Given the request and candidate items, reply with JSON "
    '{"ranking": [{"id": str, "rationale": str, "relevant": bool}]}, one entry per candidate, '
    "ordered best first. relevant is true only when the item genuinely matches the request - "
    "these are nearest neighbours from a vector search, and some can be unrelated. Don't stretch "
    "a rationale to justify a bad match; mark it false instead. Each rationale is one short "
    "sentence."
)


def justify(
    request: str, candidates: list[Candidate], query_image: bytes | None = None
) -> list[Candidate]:
    if not candidates:
        return []

    listing = [
        {
            "id": candidate.id,
            "title": candidate.title,
            "price": candidate.price,
            "colour": candidate.colour,
            "category": candidate.category,
        }
        for candidate in candidates
    ]
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"Request: {request or 'find similar items'}\nCandidates: {json.dumps(listing)}"}
    ]
    if query_image:
        content.append(image_part(query_image))

    raw = complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
        VISION,
        json_mode=True,
    )
    try:
        ranking = json.loads(raw).get("ranking", [])
    except (json.JSONDecodeError, AttributeError):
        return candidates

    by_id = {candidate.id: candidate for candidate in candidates}
    ordered: list[Candidate] = []
    for entry in ranking:
        candidate = by_id.pop(str(entry.get("id")), None)
        if not candidate or entry.get("relevant", True) is False:
            continue
        candidate.rationale = entry.get("rationale")
        ordered.append(candidate)
    # anything left in by_id is a candidate the model never mentioned (e.g. a
    # truncated response) rather than one it actively rejected - keep those
    # rather than silently dropping results because the model half-answered
    return ordered + list(by_id.values())
