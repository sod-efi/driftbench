"""Where each judge misses: recall by category and severity, and pairwise "missed by A, caught by B"
counts, from a (merged) results.json on the held-out split.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/breakdown.py results/<id>/results.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from driftbench import common


def main() -> None:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    trajectories, _ = common.load_holdout()
    meta = {t["trajectory_id"]: t for t in trajectories}
    rogue_ids = [t["trajectory_id"] for t in trajectories if t["trajectory_type"] == "rogue"]
    names = [n for n in data["results"] if n.startswith("Judge")]
    caught: dict[str, set[str]] = {}
    for name in names:
        rows = {r["id"]: r for r in data["results"][name]["trajectory_results"]}
        caught[name] = {i for i in rogue_ids if rows[i]["detected"]}

    cats = sorted({meta[i]["category"] for i in rogue_ids})
    sevs = sorted({meta[i]["severity"] for i in rogue_ids})
    print("| Judge | " + " | ".join(cats) + " | " + " | ".join(sevs) + " |")
    print("|---|" + "---|" * (len(cats) + len(sevs)))
    for name in names:
        cells = []
        for key, group in (("category", cats), ("severity", sevs)):
            for value in group:
                ids = [i for i in rogue_ids if meta[i][key] == value]
                hit = sum(1 for i in ids if i in caught[name])
                cells.append(f"{hit}/{len(ids)} ({hit/len(ids):.0%})")
        print(f"| {name} | " + " | ".join(cells) + " |")

    print("\n| Missed by | but caught by | Count |\n|---|---|---|")
    for a in names:
        for b in names:
            if a != b:
                print(f"| {a} | {b} | {len(caught[b] - caught[a])} |")
    missed_by_all = set(rogue_ids)
    for name in names:
        missed_by_all -= caught[name]
    print(f"\nRogue runs no judge caught: {len(missed_by_all)}: "
          + ", ".join(f"{i} ({meta[i]['category']} {meta[i]['severity']})" for i in sorted(missed_by_all)))
    caught_by_all = set(rogue_ids)
    for name in names:
        caught_by_all &= caught[name]
    print(f"Rogue runs every judge caught: {len(caught_by_all)} of {len(rogue_ids)}")


if __name__ == "__main__":
    main()
