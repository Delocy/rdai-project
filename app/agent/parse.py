import json

from .. import store
from ..llm import TEXT, complete
from ..schemas import Constraints
from . import rules

SYSTEM = """Extract shopping search constraints. Reply with JSON only.

Keys:
  intent            plain noun phrase describing the item, used for image search
  category          product type, or null
  colour            single colour word, or null
  price_max         number, only when an explicit budget is given, else null
  relative_cheaper  true when they want cheaper than a referenced item with no stated budget
{vocabulary}
Examples:
  "red running shoes under 40"
  {"intent": "red running shoes", "category": "Sports Shoes", "colour": "Red", "price_max": 40, "relative_cheaper": false}

  "like this but cheaper, in blue"
  {"intent": "blue item", "category": null, "colour": "Blue", "price_max": null, "relative_cheaper": true}

  "a smart leather handbag"
  {"intent": "smart leather handbag", "category": "Handbags", "colour": null, "price_max": null, "relative_cheaper": false}

intent is never an identifier, never snake_case, never empty."""

VOCABULARY = """
category: use one of the catalogue's categories below, or a word several of them share
(e.g. "Shoes" for every kind of shoe). colour: use one of the catalogue's colours below.
If the shopper asks for a product type or colour that isn't listed, give it anyway - the
search then reports that nothing matches.
  categories: {categories}
  colours: {colours}
"""


def catalogue_vocabulary() -> tuple[list[str], list[str]]:
    try:
        return store.facet_values("category"), store.facet_values("colour")
    except Exception:
        # nothing to offer (Qdrant unreachable, or a collection without the keyword
        # indexes) - parse free-form rather than fail the whole search
        return [], []


def read_rules(text: str, vocabulary: tuple[list[str], list[str]] | None = None) -> Constraints:
    """The default parser: no LLM, so it works without keys and never runs out of quota."""
    categories, colours = vocabulary if vocabulary is not None else catalogue_vocabulary()
    return rules.parse(text, categories, colours)


def parse_query(text: str, vocabulary: tuple[list[str], list[str]] | None = None) -> Constraints:
    """LLM parsing, for phrasing the rules can't follow; raises RuntimeError when no model answers."""
    if not text.strip():
        return Constraints()

    categories, colours = vocabulary if vocabulary is not None else catalogue_vocabulary()
    labels = ""
    if categories or colours:
        labels = VOCABULARY.format(categories=", ".join(categories), colours=", ".join(colours))

    raw = complete(
        [
            {"role": "system", "content": SYSTEM.replace("{vocabulary}", labels)},
            {"role": "user", "content": text},
        ],
        TEXT,
        json_mode=True,
    )
    try:
        return Constraints(**json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return Constraints(intent=text)
