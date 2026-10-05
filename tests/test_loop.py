import numpy as np
import pytest
from qdrant_client import models

from app.agent import loop
from app.config import settings
from app.schemas import Constraints, SearchResponse

# no red running shoes under 40 here, so a search for them has to relax something
CATALOGUE = [
    {"id": 1, "title": "A", "price": 45.0, "colour": "Red", "category": "Sports Shoes"},
    {"id": 2, "title": "B", "price": 48.0, "colour": "Red", "category": "Sports Shoes"},
    {"id": 3, "title": "C", "price": 30.0, "colour": "Blue", "category": "Sports Shoes"},
]


def fake_search(vector, limit, price_max=None):
    return [
        models.ScoredPoint(id=item["id"], version=0, score=1.0 - i / 10, payload=item)
        for i, item in enumerate(CATALOGUE)
        if price_max is None or item["price"] <= price_max
    ][:limit]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No LLM configured and no Qdrant: embeddings are constant and search reads CATALOGUE."""
    for name, value in (("max_iterations", 3), ("top_k", 24), ("shortlist", 5), ("llm_parse", False)):
        monkeypatch.setattr(settings(), name, value)
    monkeypatch.setattr(loop, "configured", lambda kind: False)
    monkeypatch.setattr(loop, "embed_text", lambda text: np.ones(512, dtype=np.float32))
    monkeypatch.setattr(loop.store, "search", fake_search)


def with_llm(monkeypatch, parse_by_llm: bool = True, parse=None, rank=None) -> None:
    monkeypatch.setattr(loop, "configured", lambda kind: True)
    monkeypatch.setattr(settings(), "llm_parse", parse_by_llm)
    monkeypatch.setattr(loop, "parse_query", parse or (lambda text: Constraints(intent=text)))
    monkeypatch.setattr(loop, "justify", rank or (lambda request, candidates, image=None: candidates))


def search(monkeypatch, request: Constraints, text: str = "query") -> SearchResponse:
    monkeypatch.setattr(loop, "read_rules", lambda text: request)
    return list(loop.run(text, None))[-1]


def actions(response: SearchResponse) -> list[str]:
    return [step.action for step in response.trace]


def test_without_an_llm_rules_read_the_request_and_nothing_is_degraded(monkeypatch):
    response = search(monkeypatch, Constraints(intent="running shoes", category="Sports Shoes"))
    assert (response.parser, response.ranker, response.degraded) == ("rules", "similarity", False)
    assert "read request (rules)" in actions(response)
    assert [item.title for item in response.results] == ["A", "B", "C"]


def test_a_configured_llm_ranks_and_rules_still_read_the_request_by_default(monkeypatch):
    def llm_parse(text):
        raise AssertionError("LLM parsing is off unless switched on")

    with_llm(monkeypatch, parse_by_llm=False, parse=llm_parse, rank=lambda r, c, i=None: c[::-1])
    response = search(monkeypatch, Constraints(intent="running shoes"))
    assert (response.parser, response.ranker) == ("rules", "llm")
    assert [item.title for item in response.results] == ["C", "B", "A"]


def test_switched_on_llm_parsing_reads_the_request(monkeypatch):
    with_llm(monkeypatch, parse=lambda text: Constraints(intent="shoes", colour="Blue"))
    response = search(monkeypatch, Constraints(intent="shoes"))
    assert response.parser == "llm"
    assert response.requested.colour == "Blue"


def test_a_failing_llm_falls_back_to_rules_and_similarity_and_says_so(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("no text model available")

    with_llm(monkeypatch, parse=down, rank=down)
    response = search(monkeypatch, Constraints(intent="running shoes", category="Sports Shoes"))
    assert (response.parser, response.ranker, response.degraded) == ("rules", "similarity", True)
    assert response.requested.category == "Sports Shoes"
    assert {"parse unavailable", "ranking unavailable"} <= set(actions(response))


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
    # top match A costs 45, so "cheaper" means at most 36; repair widens the ceiling to find
    # more, and whatever that lets in is labelled against the derived budget
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
