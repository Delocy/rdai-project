from types import SimpleNamespace

import numpy as np

from app import store


def test_search_skips_vectors(monkeypatch):
    request = {}

    def query_points(**kwargs):
        request.update(kwargs)
        return SimpleNamespace(points=[])

    monkeypatch.setattr(store, "client", lambda: SimpleNamespace(query_points=query_points))
    store.search(np.zeros(512, dtype=np.float32), 5, price_max=40)
    assert request["with_vectors"] is False
    assert request["query_filter"].must[0].range.lte == 40


def test_label_filters(monkeypatch):
    request = {}

    def query_points(**kwargs):
        request.update(kwargs)
        return SimpleNamespace(points=[])

    monkeypatch.setattr(store, "client", lambda: SimpleNamespace(query_points=query_points))
    store.search(np.zeros(512, dtype=np.float32), 5, categories=["Casual Shoes", "Sports Shoes"], colours=["Blue"])
    conditions = {c.key: c.match.any for c in request["query_filter"].must}
    assert conditions == {"category": ["Casual Shoes", "Sports Shoes"], "colour": ["Blue"]}


def test_empty_label_list(monkeypatch):
    monkeypatch.setattr(store, "client", lambda: None)  # would fail if called
    assert store.search(np.zeros(512, dtype=np.float32), 5, colours=[]) == []
    assert store.count_matching(categories=[]) == 0


def test_count_matching(monkeypatch):
    request = {}

    def count(collection_name, count_filter, exact):
        request.update(count_filter=count_filter, exact=exact)
        return SimpleNamespace(count=7)

    monkeypatch.setattr(store, "client", lambda: SimpleNamespace(count=count))
    assert store.count_matching(price_max=30, colours=["Pink"]) == 7
    assert request["exact"] is True
    assert len(request["count_filter"].must) == 2
