import json
from typing import Any

from ..config import settings
from ..llm import complete, image_part
from ..schemas import Candidate

SYSTEM = (
    "You rank shopping search results. Given the request and candidate items, reply with JSON "
    '{"ranking": [{"id": str, "rationale": str}]} ordered best first. '
    "Each rationale is one short sentence naming why the item fits the request."
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

    try:
        raw = complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
            settings().vision_model_list,
            json_mode=True,
        )
        ranking = json.loads(raw).get("ranking", [])
    except (RuntimeError, json.JSONDecodeError, AttributeError):
        return candidates

    by_id = {candidate.id: candidate for candidate in candidates}
    ordered: list[Candidate] = []
    for entry in ranking:
        candidate = by_id.pop(str(entry.get("id")), None)
        if candidate:
            candidate.rationale = entry.get("rationale")
            ordered.append(candidate)
    return ordered + list(by_id.values())
