"""Scores the search agent on hand-labelled queries against the sample catalogue.

Each case in eval_cases.json says what a correct result looks like (category, colour,
budget). The catalogue decides whether any such product exists, so a case with no
possible match tests that the agent says so instead of passing off near misses.

The rows build the pipeline up one stage at a time: plain CLIP retrieval; the
check/repair loop handed the right constraints; the loop reading requests with its rules
(the default - no LLM); then with an LLM ranking results, parsing requests, or both.

    python -m scripts.evaluate              # every row, using whichever LLMs the env configures
    python -m scripts.evaluate --no-vision  # skip the vision-ranking rows (slow on local models)
    python -m scripts.evaluate --no-llm     # only the rows that need no model
"""

import argparse
import json
import statistics
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app import store
from app.agent import loop
from app.agent.checks import apply, loosely_matches, words
from app.agent.justify import justify
from app.agent.parse import parse_query, read_rules
from app.config import settings
from app.llm import TEXT
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
    # results whose miss badges lie: a miss shown without one, or a fit flagged as a miss
    mislabelled: int = 0
    seconds: list[float] = field(default_factory=list)
    degraded: int = 0


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
    """Temporarily replace attributes, e.g. the parser the agent loop calls."""
    saved = {name: getattr(target, name) for name in replacements}
    for name, value in replacements.items():
        setattr(target, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(target, name, value)


@lru_cache(maxsize=None)
def llm_parsed(text: str) -> Constraints:
    # shared by the rows that parse with the LLM, so each query costs one call
    return parse_query(text)


_rankings: dict[tuple, list[tuple[str, str | None]]] = {}


def ranked_once(request: str, candidates: list[Candidate], image: bytes | None = None) -> list[Candidate]:
    """The vision model's ranking, reused when another row hands it the same shortlist."""
    key = (request, tuple(c.id for c in candidates), hash(image))
    if key not in _rankings:
        ranked = justify(request, [c.model_copy() for c in candidates], image)
        _rankings[key] = [(c.id, c.rationale) for c in ranked]
    by_id = {c.id: c for c in candidates}
    out = []
    for id, rationale in _rankings[key]:
        by_id[id].rationale = rationale
        out.append(by_id[id])
    return out


def clip_only(case: Case) -> tuple[list[Candidate], bool]:
    vector = loop.query_vector(case.query, case.image, Constraints(intent=case.query))
    kept, _ = apply(store.search(vector, K), Constraints())
    return kept, False


def agent(oracle: bool = False, parse_by_llm: bool = False, rank_by_llm: bool = False):
    def search(case: Case) -> tuple[list[Candidate], bool]:
        replacements = {
            "configured": lambda kind: parse_by_llm if kind == TEXT else rank_by_llm,
            "parse_query": llm_parsed,
            "justify": ranked_once,
        }
        if oracle:
            replacements["read_rules"] = lambda text: case.constraints()
        with swapped(loop, **replacements), swapped(settings(), llm_parse=parse_by_llm):
            response = list(loop.run(case.query, case.image))[-1]
        return response.results, response.degraded

    return search


def evaluate(cases: list[Case], system) -> Tally:
    tally = Tally()
    for number, case in enumerate(cases, 1):
        label = case.query or "(image only)"
        print(f"  [{number}/{len(cases)}] {label}", file=sys.stderr, flush=True)
        started = time.perf_counter()
        results, degraded = system(case)
        tally.seconds.append(time.perf_counter() - started)
        tally.degraded += degraded

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
        try:
            got = parse(case.query)
        except RuntimeError:
            got = Constraints()
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
    parser = argparse.ArgumentParser(description="score the search agent on labelled queries")
    parser.add_argument("--no-llm", action="store_true", help="skip the rows that call an LLM")
    parser.add_argument("--no-vision", action="store_true", help="skip the rows where a vision LLM ranks")
    args = parser.parse_args()

    cases, categories = load_cases()
    systems = [
        ("CLIP nearest neighbours", clip_only),
        ("check & repair, handed the right constraints", agent(oracle=True)),
        ("**rules - the default, no LLM**", agent()),
    ]
    if not args.no_llm:
        systems.append(("LLM parsing", agent(parse_by_llm=True)))
        if not args.no_vision:
            systems += [
                ("rules + vision LLM ranking", agent(rank_by_llm=True)),
                ("LLM parsing + vision LLM ranking", agent(parse_by_llm=True, rank_by_llm=True)),
            ]

    possible = sum(1 for case in cases if case.possible)
    print(f"{len(cases)} cases: {possible} with a possible match, {len(cases) - possible} without")
    if not args.no_llm:
        cfg = settings()
        llms = []
        if cfg.openrouter_api_key:
            llms.append(f"OpenRouter {cfg.text_models} / {cfg.vision_models}")
        if cfg.ollama_text_model or cfg.ollama_vision_model:
            llms.append(f"Ollama {cfg.ollama_text_model} / {cfg.ollama_vision_model}")
        print("LLMs (text / vision):", "; then ".join(llms) or "none configured")
    print()
    print(f"| | precision@{K} | recall@{K} | impossible requests handled | correctly labelled | median time |")
    print("|---|---|---|---|---|---|")
    for name, system in systems:
        print(name, file=sys.stderr, flush=True)
        tally = evaluate(cases, system)
        labelled = 1 - tally.mislabelled / tally.returned if tally.returned else 1.0
        note = f" ({tally.degraded} degraded)" if tally.degraded else ""
        print(
            f"| {name}{note} | {percent(tally.precision)} | {percent(tally.recall)} "
            f"| {percent(tally.impossible_handled)} | {labelled:.0%} | {statistics.median(tally.seconds):.2f}s |",
            flush=True,
        )

    print()
    print("parse accuracy on the text queries (category, colour, budget all right):")
    parsers = [("rules", read_rules)] + ([] if args.no_llm else [("LLM", llm_parsed)])
    for name, parse in parsers:
        accuracy = parse_accuracy(cases, categories, parse)
        print(f"  {name}: " + ", ".join(f"{k} {v:.0%}" for k, v in accuracy.items()))


if __name__ == "__main__":
    main()
