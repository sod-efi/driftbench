"""Merge the detector blocks of several results.json files from the same split into one
results.json (plus ci.json and summary.md), so the agreement table covers judges that
ran in different runs.

    PYTHONPATH=. .venv/Scripts/python.exe scripts/merge_results.py --out results/<id> results/a/results.json results/b/results.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from driftbench import common
from driftbench.metrics_ci import summarize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output folder under results/")
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    merged: dict = {"benchmark_info": None, "results": {}, "sources": []}
    for raw in args.inputs:
        data = json.loads(Path(raw).read_text(encoding="utf-8"))
        info = data["benchmark_info"]
        if merged["benchmark_info"] is None:
            merged["benchmark_info"] = dict(info)
        else:
            for key in ("split", "stepshield_commit", "total_trajectories"):
                if info[key] != merged["benchmark_info"][key]:
                    raise SystemExit(f"{raw}: {key} differs ({info[key]} vs {merged['benchmark_info'][key]})")
        for name, block in data["results"].items():
            if name in merged["results"]:
                raise SystemExit(f"duplicate detector {name} in {raw}")
            merged["results"][name] = block
        merged["sources"].append({"file": raw, "timestamp": info["timestamp"], "prompt_version": info.get("prompt_version")})

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    table, ci = summarize(results_path)
    (out_dir / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    info = merged["benchmark_info"]
    (out_dir / "summary.md").write_text(
        f"# {out_dir.name}\n\nMerged from {len(args.inputs)} runs; split {info['split']}; "
        f"StepShield {info['stepshield_commit'][:12]}.\n\n{table}\n",
        encoding="utf-8",
    )
    print(table)
    print(f"\nwritten: {results_path}")


if __name__ == "__main__":
    main()
