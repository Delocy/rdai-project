import numpy as np
import pytest
from qdrant_client import models

from app.search import loop
from app.config import settings
from app.schemas import Constraints, SearchResponse

# no red running shoes under 40 here, so a search for them has to relax something
CATALOGUE = [
    {"id": 1, "title": "A", "price": 45.0, "colour": "Red", "category": "Sports Shoes"},
    {"id": 2, "title": "B", "price": 48.0, "colour": "Red", "category": "Sports Shoes"},
    {"id": 3, "title": "C", "price": 30.0, "colour": "Blue", "category": "Sports Shoes"},
]


def fits(item, price_max=None, categories=None, colours=None):
    return (
        (price_max is None or item["price"] <= price_max)
        and (categories is None or item["category"] in categories)
        and (colours is None or item["colour"] in colours)
    )


def fake_search(vector, limit, price_max=None, categories=None, colours=None):
    """Stands in for Qdrant: CATALOGUE is nearest first and filters work like the real ones."""
    return [
        models.ScoredPoint(id=item["id"], version=0, score=1.0 - i / 10, payload=item)
        for i, item in enumerate(CATALOGUE)
        if fits(item, price_max, categories, colours)
    ][:limit]


def fake_count(price_max=None, categories=None, colours=None):
    return sum(fits(item, price_max, categories, colours) for item in CATALOGUE)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No Qdrant: embeddings are constant and search reads CATALOGUE."""
    for name, value in (("max_iterations", 3), ("top_k", 24), ("shortlist", 5)):
        monkeypatch.setattr(settings(), name, value)
    monkeypatch.setattr(loop, "embed_text", lambda text: np.ones(512, dtype=np.float32))
    monkeypatch.setattr(loop.store, "search", fake_search)
    monkeypatch.setattr(loop.store, "count_matching", fake_count)
    vocabulary = (sorted({i["category"] for i in CATALOGUE}), sorted({i["colour"] for i in CATALOGUE}))
    monkeypatch.setattr(loop, "catalogue_vocabulary", lambda: vocabulary)


def search(monkeypatch, request: Constraints, text: str = "query") -> SearchResponse:
    monkeypatch.setattr(loop, "read_rules", lambda text, vocabulary=None: request)
    return list(loop.run(text, None))[-1]


def actions(response: SearchResponse) -> list[str]:
    return [step.action for step in response.trace]


def test_rules_read_the_request_and_results_keep_similarity_order(monkeypatch):
    response = search(monkeypatch, Constraints(intent="running shoes", category="Sports Shoes"))
    assert actions(response)[0] == "read request"
    assert [item.title for item in response.results] == ["A", "B", "C"]


def test_a_match_beyond_the_nearest_few_is_still_found(monkeypatch):
    # only the 2 nearest come back and both are red, so the blue pair is only found if
    # the filter runs in the database
    monkeypatch.setattr(settings(), "top_k", 2)
    monkeypatch.setattr(settings(), "shortlist", 1)
    response = search(monkeypatch, Constraints(intent="blue running shoes", colour="Blue", category="Sports Shoes"))
    assert [item.title for item in response.results] == ["C"]
    assert "repair" not in actions(response)


def test_a_colour_is_only_relaxed_when_that_frees_up_matches(monkeypatch):
    # no sandals at all, so dropping "Red" changes nothing and the category goes
    response = search(monkeypatch, Constraints(intent="red sandals", colour="Red", category="Sandals"))
    repairs = [step.detail for step in response.trace if step.action == "repair"]
    assert repairs[0] == "category filter -> query text"


def test_nothing_left_after_the_repairs_says_so(monkeypatch):
    response = search(monkeypatch, Constraints(intent="sunglasses", category="Sunglasses", price_max=10))
    assert response.results == []
    assert actions(response)[-1] == "no match"


def test_response_keeps_the_request_and_reports_what_was_relaxed(monkeypatch):
    request = Constraints(intent="red running shoes", colour="Red", category="Sports Shoes", price_max=40)
    response = search(monkeypatch, request)
    assert response.requested == request
    assert response.constraints.colour is None
    assert response.constraints.price_max == 50


def test_results_that_break_the_request_say_how(monkeypatch):
    request = Constraints(intent="red running shoes", colour="Red", category="Sports Shoes", price_max=40)
    response = search(monkeypatch, request)
    assert {item.title: item.misses for item in response.results} == {
        "A": ["over budget by 5.00"],
        "B": ["over budget by 8.00"],
        "C": ["Blue, not Red"],
    }


def test_results_that_fit_carry_no_misses(monkeypatch):
    response = search(monkeypatch, Constraints(intent="running shoes", category="Sports Shoes"))
    assert [item.misses for item in response.results] == [[], [], []]


def test_a_derived_cheaper_than_budget_counts_as_the_request(monkeypatch):
    response = search(monkeypatch, Constraints(intent="shoes like this", relative_cheaper=True))
    # the top match costs 45, so "cheaper" caps at 36; repairs widen it, and results are
    # labelled against the 36
    assert response.requested.price_max == pytest.approx(36.0)
    assert {item.title: item.misses for item in response.results} == {
        "A": ["over budget by 9.00"],
        "B": ["over budget by 12.00"],
        "C": [],
    }


def test_comparison_words_alone_do_not_dilute_a_reference_photo(monkeypatch):
    embedded = []
    monkeypatch.setattr(loop, "embed_image", lambda data: np.ones(512, dtype=np.float32))
    monkeypatch.setattr(loop, "embed_text", lambda text: embedded.append(text) or np.ones(512, dtype=np.float32))
    loop.query_vector("like this but cheaper", b"photo", Constraints(intent=""))
    assert embedded == []
