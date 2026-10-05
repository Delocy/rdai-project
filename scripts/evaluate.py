"""Scores the search on the hand-labelled queries in eval_cases.json.

Each case says what a correct result looks like. Cases with no possible match check that
the search says so instead of passing off near misses. The rows add one stage at a time:
CLIP alone, the loop given the right constraints, then the loop reading requests itself.

    python -m scripts.evaluate
"""

import json
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from app import store
from app.search import loop
from app.search.checks import apply, loosely_matches, words
from app.search.parse import read_rules
from app.paths import CATALOGUE, IMAGES
from app.schemas import Candidate, Constraints
from app.seed import rows

CASES = Path(__file__).with_name("eval_cases.json")
K = 5


@dataclass
class Case:
    query: str
    image: bytes | None
    categories: list[str]
    colour: str | None
    price_max: float | None
    filter: str | None  # the category word the "right constraints" row filters on
    possible: int = 0  # catalogue products that satisfy the case

    def fits(self, category: str | None, colour: str | None, price: float) -> bool:
        return (
            (not self.categories or category in self.categories)
            and (not self.colour or loosely_matches(self.colour, colour))
            and (self.price_max is None or float(price) <= self.price_max)
        )

    def constraints(self) -> Constraints:
        return Constraints(
            intent=self.query, category=self.filter, colour=self.colour, price_max=self.price_max
        )


@dataclass
class Tally:
    precision: list[float] = field(default_factory=list)  # cases with a possible match
    recall: list[float] = field(default_factory=list)  # ...share of those matches shown
    impossible_handled: list[bool] = field(default_factory=list)  # cases with none
    returned: int = 0
    # results whose miss badges are wrong either way
    mislabelled: int = 0
    seconds: list[float] = field(default_factory=list)


def load_cases() -> tuple[list[Case], set[str]]:
    catalogue = list(rows(CATALOGUE))
    price_of = {row["image"]: float(row["price"]) for row in catalogue}
    cases = []
    for spec in json.loads(CASES.read_text(encoding="utf-8")):
        categories = spec.get("categories", [])
        price_max = spec.get("price_max")
        if spec.get("cheaper"):
            price_max = round(price_of[spec["image"]] - 0.01, 2)
        case = Case(
            query=spec["query"],
            image=(IMAGES / spec["image"]).read_bytes() if spec.get("image") else None,
            categories=categories,
            colour=spec.get("colour"),
            price_max=price_max,
            filter=spec.get("filter", categories[0] if len(categories) == 1 else None),
        )
        case.possible = sum(case.fits(r["category"], r["colour"], r["price"]) for r in catalogue)
        cases.append(case)
    return cases, {row["category"] for row in catalogue}


@contextmanager
def swapped(target, **replacements):
    """Temporarily replace attributes, e.g. the loop's parser."""
    saved = {name: getattr(target, name) for name in replacements}
    for name, value in replacements.items():
        setattr(target, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(target, name, value)


def clip_only(case: Case) -> list[Candidate]:
    vector = loop.query_vector(case.query, case.image, Constraints(intent=case.query))
    kept, _ = apply(store.search(vector, K), Constraints())
    return kept


def search_loop(oracle: bool = False):
    def search(case: Case) -> list[Candidate]:
        replacements = {"read_rules": lambda text, vocabulary=None: case.constraints()} if oracle else {}
        with swapped(loop, **replacements):
            response = list(loop.run(case.query, case.image))[-1]
        return response.results

    return search


def evaluate(cases: list[Case], system) -> Tally:
    tally = Tally()
    for number, case in enumerate(cases, 1):
        label = case.query or "(image only)"
        print(f"  [{number}/{len(cases)}] {label}", file=sys.stderr, flush=True)
        started = time.perf_counter()
        results = system(case)
        tally.seconds.append(time.perf_counter() - started)

        top = results[:K]
        fits = [case.fits(item.category, item.colour, item.price) for item in top]
        unflagged = sum(1 for item, ok in zip(top, fits) if not ok and not item.misses)
        tally.returned += len(top)
        tally.mislabelled += sum(1 for item, ok in zip(top, fits) if ok == bool(item.misses))
        if case.possible:
            tally.precision.append(sum(fits) / len(top) if top else 0.0)
            tally.recall.append(sum(fits) / min(K, case.possible))
        else:
            tally.impossible_handled.append(unflagged == 0)
    return tally


def parse_accuracy(cases: list[Case], categories: set[str], parse) -> dict[str, float]:
    def category_ok(value: str | None, gold: list[str]) -> bool:
        if not gold:
            return value is None
        if not value:
            return False
        if any(set(words(value)) == set(words(label)) for label in gold):
            return True  # named exactly the right label
        covered = {c for c in categories if loosely_matches(value, c)}
        return bool(covered) and covered <= set(gold)

    scores = {"category": [], "colour": [], "budget": [], "all three": []}
    for case in cases:
        if case.image:  # what the photo shows isn't the parser's job
            continue
        got = parse(case.query)
        checks = {
            "category": category_ok(got.category, case.categories),
            "colour": loosely_matches(case.colour, got.colour) if case.colour else got.colour is None,
            "budget": (
                got.price_max is not None and abs(got.price_max - case.price_max) < 0.01
                if case.price_max is not None
                else got.price_max is None
            ),
        }
        checks["all three"] = all(checks.values())
        for name, ok in checks.items():
            scores[name].append(ok)
    return {name: statistics.mean(values) for name, values in scores.items()}


def percent(values: list) -> str:
    return f"{statistics.mean(values):.0%}" if values else "-"


def main() -> None:
    cases, categories = load_cases()
    systems = [
        ("CLIP nearest neighbours", clip_only),
        ("check & repair, handed the right constraints", search_loop(oracle=True)),
        ("**check & repair, reading requests with the rules**", search_loop()),
    ]

    possible = sum(1 for case in cases if case.possible)
    print(f"{len(cases)} cases: {possible} with a possible match, {len(cases) - possible} without")
    print()
    print(f"| | precision@{K} | recall@{K} | impossible requests handled | correctly labelled | median time |")
    print("|---|---|---|---|---|---|")
    for name, system in systems:
        print(name, file=sys.stderr, flush=True)
        tally = evaluate(cases, system)
        labelled = 1 - tally.mislabelled / tally.returned if tally.returned else 1.0
        print(
            f"| {name} | {percent(tally.precision)} | {percent(tally.recall)} "
            f"| {percent(tally.impossible_handled)} | {labelled:.0%} | {statistics.median(tally.seconds):.2f}s |",
            flush=True,
        )

    print()
    print("rules parse accuracy on the text queries (category, colour, budget all right):")
    accuracy = parse_accuracy(cases, categories, read_rules)
    print("  " + ", ".join(f"{k} {v:.0%}" for k, v in accuracy.items()))


if __name__ == "__main__":
    main()
