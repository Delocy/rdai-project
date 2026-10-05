"""Reads a budget ("under 40"), a colour, a category and "cheaper" wording out of a request,
using the catalogue's own labels. The default parser - no model needed."""

import re

from ..schemas import Constraints
from .checks import words

_NUMBER = r"\$?\s*(\d+(?:\.\d+)?)(?:\s*(?:dollars?|bucks|usd))?"
BUDGET = re.compile(
    r"\b(?:under|below|less than|cheaper than|up to|upto|at most|no more than|max(?:imum)?|within)\s*"
    + _NUMBER
    + r"|<=?\s*"
    + _NUMBER
    + r"|\$?(\d+(?:\.\d+)?)\s*(?:dollars?|bucks|usd)?\s*or (?:less|under|below)",
    re.IGNORECASE,
)
CHEAPER = re.compile(r"\b(?:cheaper|less expensive|more affordable|lower[- ]priced?)\b", re.IGNORECASE)
FILLER = re.compile(r"\b(?:something like this|similar to this|like this|similar|but)\b", re.IGNORECASE)

# read as a colour even when the catalogue has none, so results get flagged as not that colour
COMMON_COLOURS = [
    "black", "white", "grey", "silver", "gold", "red", "orange", "yellow", "green", "blue", "navy",
    "purple", "violet", "pink", "brown", "beige", "cream", "maroon", "teal", "turquoise", "olive",
    "khaki", "tan", "mustard", "rust", "lime", "coral", "burgundy", "mint", "ivory", "indigo",
    "lavender", "magenta", "peach", "charcoal", "bronze", "copper",
]
STOP = {"and", "with", "for", "the", "a", "of", "in"}


def parse(text: str, categories: list[str], colours: list[str]) -> Constraints:
    budget = BUDGET.search(text)
    price_max = float(next(group for group in budget.groups() if group)) if budget else None
    rest = BUDGET.sub(" ", text)
    tokens = words(rest)
    return Constraints(
        intent=_intent(rest),
        category=_category(tokens, categories),
        colour=_colour(tokens, colours),
        price_max=price_max,
        relative_cheaper=price_max is None and bool(CHEAPER.search(rest)),
    )


def _intent(rest: str) -> str:
    """What the item is, for the embedding probe - without budget or comparison words."""
    cleaned = FILLER.sub(" ", CHEAPER.sub(" ", rest))
    return " ".join(re.sub(r"[^\w\s'-]", " ", cleaned).split())


def _label_words(label: str) -> list[str]:
    return [word for word in words(label) if word not in STOP]


def _category(tokens: list[str], labels: list[str]) -> str | None:
    present = set(tokens)

    # a label whose every word is in the query: the most specific one, then the one named
    # last (the head noun - "denim jacket" is a jacket)
    complete = [label for label in labels if _label_words(label) and set(_label_words(label)) <= present]
    if complete:
        return max(
            complete,
            key=lambda label: (
                len(_label_words(label)),
                max(len(tokens) - 1 - tokens[::-1].index(word) for word in _label_words(label)),
            ),
        )

    # a word that ends one or more labels: "shoes" covers Casual, Sports and Formal Shoes
    for word in reversed(tokens):
        heads = [label for label in labels if _label_words(label)[-1:] == [word]]
        if len(heads) == 1:
            return heads[0]
        if heads:
            return word.capitalize() + "s"

    # a word only one label contains, e.g. "perfume" for "Perfume and Body Mist"
    for word in reversed(tokens):
        holders = [label for label in labels if word in _label_words(label)]
        if len(holders) == 1:
            return holders[0]
    return None


def _colour(tokens: list[str], labels: list[str]) -> str | None:
    extra = [name for name in COMMON_COLOURS if not any(words(name) == words(label) for label in labels)]
    # longest names first so "Navy Blue" beats "Blue", and the catalogue's own labels first
    for name in sorted(labels + extra, key=lambda name: (-len(words(name)), name not in labels)):
        wanted = words(name)
        if any(tokens[i : i + len(wanted)] == wanted for i in range(len(tokens))):
            return name
    return None
