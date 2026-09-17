import json

from ..config import settings
from ..llm import complete
from ..schemas import Constraints

SYSTEM = (
    "Extract shopping search constraints from the user request. "
    'Reply with JSON only, keys: intent (string), category (string or null), '
    "colour (string or null), price_max (number or null), relative_cheaper (boolean). "
    "Set relative_cheaper true when the user wants something cheaper than a referenced item "
    "without naming a budget. intent is a short description of the item wanted."
)


def parse_query(text: str) -> Constraints:
    if not text.strip():
        return Constraints()

    # every model failing is expected on free tiers; fall back to pure vector search
    try:
        raw = complete(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
            settings().text_model_list,
            json_mode=True,
        )
        return Constraints(**json.loads(raw))
    except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
        return Constraints(intent=text)
