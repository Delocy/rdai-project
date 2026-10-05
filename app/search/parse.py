from .. import store
from ..schemas import Constraints
from . import rules


def catalogue_vocabulary() -> tuple[list[str], list[str]]:
    try:
        return store.facet_values("category"), store.facet_values("colour")
    except Exception:
        # no labels (Qdrant down, or no keyword indexes), so read the request without them
        return [], []


def read_rules(text: str, vocabulary: tuple[list[str], list[str]] | None = None) -> Constraints:
    """Reads budget, colour and category from the request using the catalogue's labels."""
    categories, colours = vocabulary if vocabulary is not None else catalogue_vocabulary()
    return rules.parse(text, categories, colours)
