from qdrant_client import models

from app.search.checks import apply, loosely_matches, misses
from app.search.loop import repair
from app.schemas import Candidate, Constraints


def point(price: float, category: str = "shoes", colour: str | None = None) -> models.ScoredPoint:
    return models.ScoredPoint(
        id="00000000-0000-0000-0000-00000000000{}".format(int(price) % 10),
        version=0,
        score=0.5,
        payload={"title": "item", "price": price, "category": category, "colour": colour},
        vector=[0.0] * 512,
    )


NONE_REJECTED = {"wrong_colour": 0, "wrong_category": 0}


def more_without(field: str):
    """Counts that rise once `field` is dropped, so that constraint is the one in the way."""
    return lambda constraints: 5 if getattr(constraints, field) is None else 0


def nothing_helps(constraints: Constraints) -> int:
    return 0


def test_no_constraints_keeps_everything():
    kept, rejected = apply([point(10), point(200)], Constraints())
    assert len(kept) == 2
    assert rejected == NONE_REJECTED


def test_price_is_left_to_the_server_side_filter():
    kept, _ = apply([point(10), point(200)], Constraints(price_max=50))
    assert len(kept) == 2


def test_colour_matches_compound_names_either_way():
    kept, rejected = apply(
        [point(10, colour="Navy Blue"), point(20, colour="Red")], Constraints(colour="blue")
    )
    assert [c.colour for c in kept] == ["Navy Blue"]
    assert rejected["wrong_colour"] == 1


def test_missing_colour_rejected():
    kept, _ = apply([point(10, colour=None)], Constraints(colour="blue"))
    assert kept == []


def test_category_casing_and_plurals():
    kept, rejected = apply(
        [point(10, category="Watches"), point(20, category="Shirts")],
        Constraints(category="watches"),
    )
    assert [c.category for c in kept] == ["Watches"]
    assert rejected["wrong_category"] == 1


def test_repair_moves_colour_to_probe():
    repaired, note = repair(
        Constraints(intent="running shoes", price_max=50, colour="blue"),
        more_without("colour"),
    )
    assert repaired.colour is None
    assert repaired.intent == "blue running shoes"
    assert repaired.price_max == 50
    assert "colour" in note


def test_repair_moves_category_to_probe():
    repaired, note = repair(
        Constraints(intent="something black", category="watches"),
        more_without("category"),
    )
    assert repaired.category is None
    assert repaired.intent == "watches something black"
    assert "category" in note


def test_repair_no_duplicate_colour():
    repaired, _ = repair(
        Constraints(intent="blue top", colour="Blue"), more_without("colour")
    )
    assert repaired.intent == "blue top"


def test_repair_widens_price():
    repaired, note = repair(Constraints(price_max=50), nothing_helps)
    assert repaired.price_max == 62.5
    assert "price" in note


def test_repair_gives_up():
    repaired, note = repair(Constraints(), nothing_helps)
    assert note == ""
    assert repaired == Constraints()


def test_misses_describe_each_problem():
    item = Candidate(id="1", title="t", price=45.0, colour="Red", category="Casual Shoes", score=0.5)
    request = Constraints(price_max=40, colour="blue", category="Sports Shoes")
    assert misses(item, request) == ["over budget by 5.00", "Red, not blue", "Casual Shoes, not Sports Shoes"]


def test_no_misses_when_it_fits():
    item = Candidate(id="1", title="t", price=30.0, colour="Navy Blue", category="Shirts", score=0.5)
    assert misses(item, Constraints(price_max=40, colour="blue", category="shirts")) == []


def test_shirts_excludes_tshirts():
    kept, rejected = apply(
        [point(10, category="Shirts"), point(20, category="Tshirts"), point(30, category="Sweatshirts")],
        Constraints(category="Shirts"),
    )
    assert [c.category for c in kept] == ["Shirts"]
    assert rejected["wrong_category"] == 2


def test_whole_words_not_substrings():
    assert not loosely_matches("Shirts", "Tshirts")
    assert not loosely_matches("Ring", "Earrings")
    assert not loosely_matches("Bra", "Bracelet")


def test_ignores_plurals_case_hyphens():
    assert loosely_matches("watch", "Watches")
    assert loosely_matches("dress", "Dresses")
    assert loosely_matches("t-shirt", "Tshirts")
    assert loosely_matches("Shoes", "Casual Shoes")


def test_synonyms():
    assert loosely_matches("sneakers", "Casual Shoes")
    assert loosely_matches("running shoes", "Sports Shoes")
    assert loosely_matches("tee", "Tshirts")
    assert loosely_matches("gray", "Grey")
    assert loosely_matches("purse", "Handbags")


def test_repair_budget_before_category():
    # every sports shoe costs over 40, so widen the budget rather than drop the category
    repaired, note = repair(
        Constraints(intent="running shoes", category="Sports Shoes", price_max=40),
        more_without("category"),
    )
    assert repaired.category == "Sports Shoes"
    assert repaired.price_max == 50
    assert "price" in note


def test_repair_skips_colour_that_doesnt_help():
    repaired, note = repair(Constraints(intent="red sandals", colour="Red", category="Sandals"), more_without("category"))
    assert repaired.colour == "Red"
    assert "category" in note
