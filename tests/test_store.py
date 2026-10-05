from types import SimpleNamespace

import numpy as np

from app import store


def test_search_leaves_the_stored_vectors_out_of_the_response(monkeypatch):
    request = {}

    def query_points(**kwargs):
        request.update(kwargs)
        return SimpleNamespace(points=[])

    monkeypatch.setattr(store, "client", lambda: SimpleNamespace(query_points=query_points))
    store.search(np.zeros(512, dtype=np.float32), 5, price_max=40)
    assert request["with_vectors"] is False
    assert request["query_filter"].must[0].range.lte == 40
