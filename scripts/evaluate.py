import argparse

from app import store
from app.agent.checks import apply, loosely_matches
from app.embeddings import embed_text
from app.schemas import Constraints

TOP_K = 24

# query, expected colour, expected category substring
CASES = [
    ("a black watch", "black", "Watches"),
    ("blue shirt", "blue", "Shirts"),
    ("white tshirt", "white", "Tshirts"),
    ("red sports shoes", "red", "Shoes"),
    ("brown handbag", "brown", "Handbags"),
    ("pink top", "pink", "Tops"),
    ("navy blue casual shoes", "blue", "Shoes"),
    ("black flip flops", "black", "Flip Flops"),
    ("grey tshirt", "grey", "Tshirts"),
    ("white sandals", "white", "Sandals"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="measure retrieval precision at k")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    raw_totals = {"colour": 0.0, "category": 0.0}
    agent_totals = {"colour": 0.0, "category": 0.0}
    print(f"{'query':26} {'raw col':>8} {'agent col':>10} {'raw cat':>8} {'agent cat':>10}")

    for query, colour, category in CASES:
        vector = embed_text(query)
        raw = [p.payload or {} for p in store.search(vector, args.k)]
        kept, _ = apply(store.search(vector, TOP_K), Constraints(intent=query, colour=colour))
        agent = [{"colour": c.colour, "category": c.category} for c in kept[: args.k]]

        scores = []
        for payloads in (raw, agent):
            if not payloads:
                scores.append((0.0, 0.0))
                continue
            scores.append((
                sum(loosely_matches(colour, p.get("colour")) for p in payloads) / len(payloads),
                sum(loosely_matches(category, p.get("category")) for p in payloads) / len(payloads),
            ))
        (rc, rg), (ac, ag) = scores

        raw_totals["colour"] += rc
        raw_totals["category"] += rg
        agent_totals["colour"] += ac
        agent_totals["category"] += ag
        print(f"{query:26} {rc:8.0%} {ac:10.0%} {rg:8.0%} {ag:10.0%}")

    n = len(CASES)
    print()
    print(f"mean p@{args.k} colour   raw {raw_totals['colour']/n:.0%} -> agent {agent_totals['colour']/n:.0%}")
    print(f"mean p@{args.k} category raw {raw_totals['category']/n:.0%} -> agent {agent_totals['category']/n:.0%}")


if __name__ == "__main__":
    main()
