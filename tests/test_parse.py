from app.search import parse


def test_labels_are_read_from_the_catalogue_when_not_given(monkeypatch):
    labels = {"category": ["Watches"], "colour": ["Gold"]}
    monkeypatch.setattr(parse.store, "facet_values", lambda key: labels[key])
    constraints = parse.read_rules("gold watch")
    assert (constraints.category, constraints.colour) == ("Watches", "Gold")


def test_a_request_is_still_read_when_the_catalogue_labels_cannot_be(monkeypatch):
    def unreachable(key):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(parse.store, "facet_values", unreachable)
    assert parse.read_rules("watch under 40").price_max == 40
