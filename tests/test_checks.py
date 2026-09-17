from qdrant_client import models

from app.agent.checks import apply
from app.agent.loop import repair
from app.schemas import Constraints


def point(price: float, category: str = "shoes") -> models.ScoredPoint:
    return models.ScoredPoint(
        id="00000000-0000-0000-0000-00000000000{}".format(int(price) % 10),
        version=0,
        score=0.5,
        payload={"title": "item", "price": price, "category": category},
        vector=[0.0] * 512,
    )


def test_price_ceiling_rejects_expensive_items():
    kept, rejected = apply([point(10), point(200)], Constraints(price_max=50))
    assert [c.price for c in kept] == [10]
    assert rejected["over_price"] == 1


def test_no_constraints_keeps_everything():
    kept, rejected = apply([point(10), point(200)], Constraints())
    assert len(kept) == 2
    assert rejected == {"over_price": 0, "wrong_colour": 0}


def test_repair_widens_price_before_dropping_colour():
    constraints = Constraints(price_max=50, colour="blue")
    repaired, note = repair(constraints, {"over_price": 3, "wrong_colour": 1})
    assert repaired.price_max == 62.5
    assert repaired.colour == "blue"
    assert "price" in note


def test_repair_gives_up_when_nothing_left_to_relax():
    repaired, note = repair(Constraints(), {"over_price": 0, "wrong_colour": 0})
    assert note == ""
    assert repaired == Constraints()
