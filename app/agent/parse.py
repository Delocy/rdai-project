import json

from ..llm import TEXT, complete
from ..schemas import Constraints

SYSTEM = """Extract shopping search constraints. Reply with JSON only.

Keys:
  intent            plain noun phrase describing the item, used for image search
  category          product type, or null
  colour            single colour word, or null
  price_max         number, only when an explicit budget is given, else null
  relative_cheaper  true when they want cheaper than a referenced item with no stated budget

Examples:
  "red running shoes under 40"
  {"intent": "red running shoes", "category": "shoes", "colour": "red", "price_max": 40, "relative_cheaper": false}

  "like this but cheaper, in blue"
  {"intent": "blue item", "category": null, "colour": "blue", "price_max": null, "relative_cheaper": true}

  "a smart leather handbag"
  {"intent": "smart leather handbag", "category": "handbags", "colour": null, "price_max": null, "relative_cheaper": false}

intent is never an identifier, never snake_case, never empty."""


def parse_query(text: str) -> Constraints:
    if not text.strip():
        return Constraints()

    raw = complete(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        TEXT,
        json_mode=True,
    )
    try:
        return Constraints(**json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return Constraints(intent=text)
