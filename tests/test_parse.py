import json

from app.agent import parse
from app.schemas import Constraints

VOCABULARY = (["Casual Shoes", "Sports Shoes", "Tshirts", "Watches"], ["Black", "Navy Blue", "White"])


def model_replies(monkeypatch, reply: dict) -> list:
    """Make the text model answer with `reply`; returns the list each request's messages land in."""
    sent = []

    def fake_complete(messages, kind, json_mode=False):
        sent.append(messages)
        return json.dumps(reply)

    monkeypatch.setattr(parse, "complete", fake_complete)
    return sent


def test_prompt_offers_the_catalogue_labels(monkeypatch):
    sent = model_replies(monkeypatch, {"intent": "white sneakers", "category": "Casual Shoes"})
    parse.parse_query("white sneakers", VOCABULARY)
    system = sent[0][0]["content"]
    assert "Casual Shoes" in system
    assert "Navy Blue" in system


def test_catalogue_labels_are_kept_as_filters(monkeypatch):
    model_replies(monkeypatch, {"intent": "white sneakers", "category": "Casual Shoes", "colour": "White"})
    constraints = parse.parse_query("white sneakers", VOCABULARY)
    assert (constraints.category, constraints.colour) == ("Casual Shoes", "White")


def test_a_word_several_categories_share_is_kept(monkeypatch):
    model_replies(monkeypatch, {"intent": "shoes", "category": "Shoes"})
    assert parse.parse_query("shoes", VOCABULARY).category == "Shoes"


def test_a_category_the_catalogue_lacks_is_kept_so_results_get_flagged(monkeypatch):
    # the loop relaxes it when nothing matches and labels every result against it
    model_replies(monkeypatch, {"intent": "laptop", "category": "Laptops"})
    assert parse.parse_query("laptop", VOCABULARY).category == "Laptops"


def test_a_colour_the_catalogue_lacks_is_kept_so_results_get_flagged(monkeypatch):
    model_replies(monkeypatch, {"intent": "teal watch", "colour": "teal"})
    assert parse.parse_query("teal watch", VOCABULARY).colour == "teal"


def test_without_catalogue_labels_the_model_output_is_used_as_is(monkeypatch):
    model_replies(monkeypatch, {"intent": "running gear", "category": "sneakers"})
    assert parse.parse_query("running gear", ([], [])).category == "sneakers"


def test_labels_are_read_from_the_catalogue_when_not_given(monkeypatch):
    sent = model_replies(monkeypatch, {"intent": "gold watch"})
    labels = {"category": ["Watches"], "colour": ["Gold"]}
    monkeypatch.setattr(parse.store, "facet_values", lambda key: labels[key])
    parse.parse_query("gold watch")
    system = sent[0][0]["content"]
    assert "Watches" in system
    assert "Gold" in system


def test_parse_still_works_when_the_catalogue_labels_cannot_be_read(monkeypatch):
    model_replies(monkeypatch, {"intent": "watch", "category": "watches"})

    def unreachable(key):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(parse.store, "facet_values", unreachable)
    assert parse.parse_query("watch").category == "watches"


def test_unreadable_reply_falls_back_to_the_raw_text(monkeypatch):
    monkeypatch.setattr(parse, "complete", lambda *args, **kwargs: "not json")
    assert parse.parse_query("blue shirt", VOCABULARY) == Constraints(intent="blue shirt")
