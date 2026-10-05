import pytest

from app.search import rules

CATEGORIES = [
    "Casual Shoes", "Sports Shoes", "Formal Shoes", "Shoe Accessories", "Tshirts", "Shirts",
    "Sweatshirts", "Watches", "Handbags", "Laptop Bag", "Jackets", "Jeans", "Kurtas", "Kurta Sets",
    "Perfume and Body Mist", "Flip Flops", "Sunglasses", "Tops", "Track Pants", "Lounge Pants",
]
COLOURS = ["Black", "White", "Blue", "Navy Blue", "Grey", "Red", "Pink", "Brown", "Off White", "Gold"]


def read(text: str):
    return rules.parse(text, CATEGORIES, COLOURS)


@pytest.mark.parametrize(
    "text, category, colour, price_max",
    [
        ("black watch", "Watches", "Black", None),
        ("pink top under 30", "Tops", "Pink", 30),
        ("navy blue shirt", "Shirts", "Navy Blue", None),
        ("grey t-shirt", "Tshirts", "Grey", None),
        ("gray tee", "Tshirts", "Grey", None),
        ("white sneakers", "Shoes", "White", None),
        ("red running shoes under 40", "Sports Shoes", "Red", 40),
        ("black formal shoes below $100", "Formal Shoes", "Black", 100),
        ("blue denim jacket", "Jackets", "Blue", None),
        ("perfume less than 25.50", "Perfume and Body Mist", None, 25.5),
        ("watches up to 150 dollars", "Watches", None, 150),
        ("kurta", "Kurtas", None, None),
        ("pants", "Pants", None, None),
        ("something nice", None, None, None),
    ],
)
def test_rules_read_category_colour_and_budget(text, category, colour, price_max):
    constraints = read(text)
    assert (constraints.category, constraints.colour, constraints.price_max) == (category, colour, price_max)


def test_unknown_colour_still_read():
    assert read("teal watch").colour == "teal"


def test_cheaper_without_number():
    constraints = read("like this but cheaper")
    assert constraints.relative_cheaper is True
    assert constraints.price_max is None


def test_cheaper_than_a_number_is_a_budget():
    constraints = read("cheaper than 40")
    assert constraints.price_max == 40
    assert constraints.relative_cheaper is False


def test_intent_drops_budget_words():
    assert read("pink top under 30").intent == "pink top"
    assert read("like this but cheaper").intent == ""


def test_reads_without_labels():
    constraints = rules.parse("black watch under 50", [], [])
    assert (constraints.category, constraints.colour, constraints.price_max) == (None, "black", 50)
