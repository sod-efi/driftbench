"""Re-judge the trajectories a budget stop left unfinished, and recompute the run.

A judge that hits its hard budget stop marks the remaining steps "budget stop"
(no API call, verdict "not rogue"), which would bias recall downward. Because
each step is judged on its own at temperature 0, re-running only the affected
trajectories with the same prompt and model is methodologically clean. This
command does that, rewrites the affected rows in results.json and the step log,
recomputes the metrics and the summary, and records what it did.

  python -m driftbench.repair --run-id 2026-10-26-holdout-judges --budget-usd 0.20
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from . import common
from .metrics_ci import summarize
from .run import to_block

common.load_env()

from metrics.timing_metrics import calculate_metrics  # vendor  # noqa: E402
from run_benchmark import run_detector  # vendor  # noqa: E402


async def repair(run_id: str, budget_usd: float) -> None:
    from .judge import OpenRouterJudge

    out_dir = common.RESULTS / run_id
    results_path = out_dir / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    split = data["benchmark_info"]["split"]
    trajectories = common.load_holdout()[0] if split == "holdout" else common.load_dev_split()
    by_id = {t["trajectory_id"]: t for t in trajectories}
    prompt_version = data["benchmark_info"]["prompt_version"]

    for name, block in data["results"].items():
        if not name.startswith("Judge-"):
            continue
        log_path = next(out_dir.glob(f"steps-*-{prompt_version}.jsonl"), None)
        logs = [
            p for p in out_dir.glob(f"steps-*-{prompt_version}.jsonl")
            if name.split("-", 1)[1].rsplit("-", 1)[0] in p.name.replace("_", "/").replace("anthropic/", "").replace("openai/", "").replace("google/", "")
        ]
        log_path = logs[0] if logs else log_path
        if log_path is None:
            print(f"{name}: no step log found, skipped")
            continue
        rows = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        logged: dict[str, set[int]] = {}
        for r in rows:
            if (r.get("reason") or "") != "budget stop":
                logged.setdefault(r["trajectory_id"], set()).add(r["step"])
        stopped_ids = sorted(
            row["id"] for row in block["trajectory_results"]
            if len(logged.get(row["id"], set())) < len(by_id[row["id"]]["steps"])
        )
        if not stopped_ids:
            print(f"{name}: nothing to repair")
            continue
        model = rows[0]["model"]
        print(f"{name}: {len(stopped_ids)} trajectories to re-judge with {model}")
        judge = OpenRouterJudge(model=model, prompt_version=prompt_version, log_path=out_dir / f"repair-{log_path.name}", budget_usd=budget_usd)
        redo = [by_id[i] for i in stopped_ids if i in by_id]
        new_results = await run_detector(judge, redo)
        if judge.budget_exceeded:
            print(f"   WARNING: repair hit its own budget stop at ${judge.total_cost:.2f}; rerun with a larger budget")
        # Merge: replace affected trajectory rows, then rebuild the block from all rows.
        new_rows = {
            r.trajectory_id: {
                "id": r.trajectory_id, "type": r.trajectory_type, "category": r.category, "total_steps": r.total_steps,
                "detected": r.detected, "detection_step": r.detection_step, "ground_truth_step": r.ground_truth_step,
                "intervention_gap": r.intervention_gap, "is_early": r.is_early,
            }
            for r in new_results
        }
        merged = [new_rows.get(row["id"], row) for row in block["trajectory_results"]]
        # Recompute aggregate metrics from TrajectoryResult objects: rebuild them from rows.
        from metrics.timing_metrics import TrajectoryResult  # vendor

        objs = [
            TrajectoryResult(
                trajectory_id=m["id"], trajectory_type=m["type"], category=m["category"], total_steps=m["total_steps"],
                ground_truth_step=m["ground_truth_step"], detection_step=m["detection_step"], detected=m["detected"],
                intervention_gap=m["intervention_gap"], is_early=m["is_early"], tokens_saved=None,
            )
            for m in merged
        ]
        metrics = calculate_metrics(objs)
        old_cost = block["cost"]
        new_block = to_block(name, objs, metrics, block["elapsed_seconds"], judge)
        new_block["cost"] = {
            "api_calls": old_cost["api_calls"] + judge.api_calls,
            "total_tokens": old_cost["total_tokens"] + judge.total_tokens,
            "total_cost_usd": round(old_cost["total_cost_usd"] + judge.total_cost, 4),
            "budget_exceeded": judge.budget_exceeded,
            "repaired": {
                "time": datetime.now(timezone.utc).isoformat(),
                "trajectories": stopped_ids,
                "repair_cost_usd": round(judge.total_cost, 4),
            },
        }
        data["results"][name] = new_block
        # Rewrite the step log: drop the budget-stop rows, append the repair rows.
        kept = [r for r in rows if (r.get("reason") or "") != "budget stop"]
        repair_rows = [json.loads(l) for l in judge.log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        with log_path.open("w", encoding="utf-8") as handle:
            for r in kept + repair_rows:
                handle.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"   repaired; extra cost ${judge.total_cost:.2f}; recall now {metrics.recall*100:.1f}%")

    results_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    table, ci = summarize(results_path)
    (out_dir / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(
        f"# {run_id}\n\nSplit: {split}; StepShield {data['benchmark_info']['stepshield_commit'][:12]}; prompt {prompt_version}; "
        f"repaired {datetime.now(timezone.utc).date()}.\n\n{table}\n", encoding="utf-8")
    print("\n" + table)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--budget-usd", type=float, default=0.25)
    args = parser.parse_args()
    asyncio.run(repair(args.run_id, args.budget_usd))


if __name__ == "__main__":
    main()
