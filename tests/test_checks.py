from qdrant_client import models

from app.agent.checks import apply, loosely_matches, misses
from app.agent.loop import repair
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


def test_missing_colour_metadata_is_rejected_when_colour_requested():
    kept, _ = apply([point(10, colour=None)], Constraints(colour="blue"))
    assert kept == []


def test_category_tolerates_model_casing_and_plurals():
    kept, rejected = apply(
        [point(10, category="Watches"), point(20, category="Shirts")],
        Constraints(category="watches"),
    )
    assert [c.category for c in kept] == ["Watches"]
    assert rejected["wrong_category"] == 1


def test_repair_moves_colour_into_the_query_probe():
    repaired, note = repair(
        Constraints(intent="running shoes", price_max=50, colour="blue"),
        {**NONE_REJECTED, "wrong_colour": 4},
    )
    assert repaired.colour is None
    assert repaired.intent == "blue running shoes"
    assert repaired.price_max == 50
    assert "colour" in note


def test_repair_moves_category_into_the_query_probe():
    repaired, note = repair(
        Constraints(intent="something black", category="watches"),
        {**NONE_REJECTED, "wrong_category": 9},
    )
    assert repaired.category is None
    assert repaired.intent == "watches something black"
    assert "category" in note


def test_repair_does_not_duplicate_a_colour_already_in_the_probe():
    repaired, _ = repair(
        Constraints(intent="blue top", colour="Blue"), {**NONE_REJECTED, "wrong_colour": 2}
    )
    assert repaired.intent == "blue top"


def test_repair_widens_price_when_filters_are_not_the_problem():
    repaired, note = repair(Constraints(price_max=50), NONE_REJECTED)
    assert repaired.price_max == 62.5
    assert "price" in note


def test_repair_gives_up_when_nothing_left_to_relax():
    repaired, note = repair(Constraints(), NONE_REJECTED)
    assert note == ""
    assert repaired == Constraints()


def test_misses_spells_out_how_a_result_breaks_the_request():
    item = Candidate(id="1", title="t", price=45.0, colour="Red", category="Casual Shoes", score=0.5)
    request = Constraints(price_max=40, colour="blue", category="Sports Shoes")
    assert misses(item, request) == ["over budget by 5.00", "Red, not blue", "Casual Shoes, not Sports Shoes"]


def test_misses_is_empty_when_a_result_fits_the_request():
    item = Candidate(id="1", title="t", price=30.0, colour="Navy Blue", category="Shirts", score=0.5)
    assert misses(item, Constraints(price_max=40, colour="blue", category="shirts")) == []


def test_a_shirt_filter_rejects_tshirts_and_sweatshirts():
    kept, rejected = apply(
        [point(10, category="Shirts"), point(20, category="Tshirts"), point(30, category="Sweatshirts")],
        Constraints(category="Shirts"),
    )
    assert [c.category for c in kept] == ["Shirts"]
    assert rejected["wrong_category"] == 2


def test_labels_match_on_whole_words_not_substrings():
    assert not loosely_matches("Shirts", "Tshirts")
    assert not loosely_matches("Ring", "Earrings")
    assert not loosely_matches("Bra", "Bracelet")


def test_matching_ignores_plurals_case_and_hyphens():
    assert loosely_matches("watch", "Watches")
    assert loosely_matches("dress", "Dresses")
    assert loosely_matches("t-shirt", "Tshirts")
    assert loosely_matches("Shoes", "Casual Shoes")


def test_everyday_words_match_the_catalogue_labels():
    assert loosely_matches("sneakers", "Casual Shoes")
    assert loosely_matches("running shoes", "Sports Shoes")
    assert loosely_matches("tee", "Tshirts")
    assert loosely_matches("gray", "Grey")
    assert loosely_matches("purse", "Handbags")


def test_repair_widens_the_budget_before_giving_up_the_category():
    # every sports shoe costs over 40: relax the budget, not what kind of thing it is
    repaired, note = repair(
        Constraints(intent="running shoes", category="Sports Shoes", price_max=40),
        {**NONE_REJECTED, "wrong_category": 24},
    )
    assert repaired.category == "Sports Shoes"
    assert repaired.price_max == 50
    assert "price" in note
