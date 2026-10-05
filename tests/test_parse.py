from app.search import parse


def test_uses_catalogue_labels(monkeypatch):
    labels = {"category": ["Watches"], "colour": ["Gold"]}
    monkeypatch.setattr(parse.store, "facet_values", lambda key: labels[key])
    constraints = parse.read_rules("gold watch")
    assert (constraints.category, constraints.colour) == ("Watches", "Gold")


def test_reads_without_labels(monkeypatch):
    def unreachable(key):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(parse.store, "facet_values", unreachable)
    assert parse.read_rules("watch under 40").price_max == 40
