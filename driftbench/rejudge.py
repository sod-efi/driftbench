"""Re-judge the steps whose verdict was a harness failure, not a judgment, and recompute the run.

StepShield's judge caps answers at 200 output tokens and its parser returns "Parse error"
(verdict: not rogue) when the JSON is cut off. Claude models write long reasons, so 27% of
Haiku's and 7% of Sonnet's answers on the held-out set were never read. Each step is judged
on its own at temperature 0, so re-asking only those steps with a larger cap, the same prompt
and the same model is methodologically clean. This command does that for every judge log in a
run (or for one bare step log), rewrites the affected rows, recomputes the metrics and the
summary, and records what it did.

  python -m driftbench.rejudge --run-id 2026-10-27-holdout-judges-2 --budget-usd 1.8
  python -m driftbench.rejudge --log results/<calibrate-run>/steps-v1.jsonl --split dev --pairs-per-category 6 --budget-usd 0.2
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import common
from .judge import DEFAULT_MAX_TOKENS, OpenRouterJudge, is_failed_row, is_refused_row
from .metrics_ci import summarize
from .run import to_block

common.load_env()

from metrics.timing_metrics import (  # vendor  # noqa: E402
    TrajectoryResult,
    calculate_intervention_gap,
    calculate_metrics,
    is_early_intervention,
)


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


INCLUDE_REFUSED = False


def is_failed(row: dict[str, Any]) -> bool:
    if (row.get("reason") or "") == "budget stop":
        return False
    return is_failed_row(row) or (INCLUDE_REFUSED and is_refused_row(row))


def context_for(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": trajectory.get("task", {}),
        "trajectory_type": trajectory.get("trajectory_type"),
        "category": trajectory.get("category", "UNK"),
        "trajectory_id": trajectory["trajectory_id"],
        "rogue_step": trajectory.get("rogue_step"),
    }


async def rejudge_log(
    log_path: Path, by_id: dict[str, dict[str, Any]], budget_usd: float, max_tokens: int
) -> tuple[list[dict[str, Any]], OpenRouterJudge | None, dict[str, Any]]:
    """Re-ask the failed steps of one log. Returns the merged rows, the judge used, and a record."""
    rows = read_rows(log_path)
    failed = [r for r in rows if is_failed(r)]
    record: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
        "failed_before": len(failed),
        "max_tokens": max_tokens,
    }
    if not failed:
        return rows, None, record
    model, version = rows[0]["model"], rows[0]["prompt_version"]
    judge = OpenRouterJudge(
        model=model,
        prompt_version=version,
        log_path=log_path.with_name("rejudge-" + log_path.name),
        budget_usd=budget_usd,
        max_tokens=max_tokens,
    )
    print(f"{log_path.name}: {len(failed)} failed steps to re-judge with {model} (max_tokens {max_tokens})")
    tasks = []
    for r in failed:
        trajectory = by_id[r["trajectory_id"]]
        step = trajectory["steps"][r["step"] - 1]
        tasks.append(judge.detect_step(step, r["step"], context_for(trajectory)))
    await asyncio.gather(*tasks)
    if judge.budget_exceeded:
        print(f"   WARNING: re-judging hit its budget stop at ${judge.total_cost:.2f}; rerun with a larger budget")
    new_rows = {(r["trajectory_id"], r["step"]): r for r in read_rows(judge.log_path)}
    merged = [new_rows.get((r["trajectory_id"], r["step"]), r) for r in rows]
    still = sum(1 for r in merged if is_failed(r))
    record.update(
        {
            "rejudged": len(new_rows),
            "failed_after": still,
            "cost_usd": round(judge.total_cost, 4),
            "now_rogue": sum(1 for r in new_rows.values() if r["is_rogue"]),
        }
    )
    print(
        f"   re-judged {len(new_rows)}; rogue on {record['now_rogue']} of them; still failed {still}; "
        f"cost ${judge.total_cost:.2f}"
    )
    return merged, judge, record


def rebuild(rows: list[dict[str, Any]], order: list[dict[str, Any]]) -> list[TrajectoryResult]:
    """Trajectory results from a step log: the first flagged step is the detection step."""
    first_alert: dict[str, int] = {}
    for r in sorted(rows, key=lambda r: (r["trajectory_id"], r["step"])):
        if r["is_rogue"] and r["trajectory_id"] not in first_alert:
            first_alert[r["trajectory_id"]] = r["step"]
    objs = []
    for row in order:
        detection = first_alert.get(row["id"])
        truth = row["ground_truth_step"]
        objs.append(
            TrajectoryResult(
                trajectory_id=row["id"],
                trajectory_type=row["type"],
                category=row["category"],
                total_steps=row["total_steps"],
                ground_truth_step=truth,
                detection_step=detection,
                detected=detection is not None,
                intervention_gap=calculate_intervention_gap(detection, truth),
                is_early=is_early_intervention(detection, truth),
                tokens_saved=None,
            )
        )
    return objs


async def rejudge_run(run_id: str, budget_usd: float, max_tokens: int) -> None:
    out_dir = common.RESULTS / run_id
    results_path = out_dir / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    split = data["benchmark_info"]["split"]
    trajectories = common.load_holdout()[0] if split == "holdout" else common.load_dev_split()
    by_id = {t["trajectory_id"]: t for t in trajectories}
    prompt_version = data["benchmark_info"]["prompt_version"]
    logs: dict[str, Path] = {}
    for path in out_dir.glob(f"steps-*-{prompt_version}.jsonl"):
        first = read_rows(path)[0]
        logs[f"Judge-{first['model'].split('/')[-1]}-{prompt_version}"] = path

    remaining = budget_usd
    for name, block in data["results"].items():
        if not name.startswith("Judge-"):
            continue
        if name not in logs:
            print(f"{name}: no step log found, skipped")
            continue
        merged, judge, record = await rejudge_log(logs[name], by_id, remaining, max_tokens)
        if judge is None:
            print(f"{name}: nothing to re-judge")
            continue
        remaining -= judge.total_cost
        objs = rebuild(merged, block["trajectory_results"])
        metrics = calculate_metrics(objs)
        old_cost = block["cost"]
        new_block = to_block(name, objs, metrics, block["elapsed_seconds"], judge)
        new_block["cost"] = {
            **old_cost,
            "api_calls": old_cost["api_calls"] + judge.api_calls,
            "total_tokens": old_cost["total_tokens"] + judge.total_tokens,
            "total_cost_usd": round(old_cost["total_cost_usd"] + judge.total_cost, 4),
            "budget_exceeded": judge.budget_exceeded,
            "rejudged": record,
        }
        data["results"][name] = new_block
        write_rows(logs[name], merged)
        cm = new_block["confusion_matrix"]
        fpr = cm["fp"] / max(1, cm["fp"] + cm["tn"]) * 100
        print(f"   recall now {metrics.recall * 100:.1f}%, FPR {fpr:.1f}%, EIR {metrics.eir:.2f}")

    results_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    table, ci = summarize(results_path)
    (out_dir / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(
        f"# {run_id}\n\nSplit: {split}; StepShield {data['benchmark_info']['stepshield_commit'][:12]}; "
        f"prompt {prompt_version}; failed steps re-judged {datetime.now(timezone.utc).date()} "
        f"(max_tokens {max_tokens}).\n\n{table}\n",
        encoding="utf-8",
    )
    print("\n" + table)


async def rejudge_bare_log(log_path: Path, split: str, pairs_per_category: int, budget_usd: float, max_tokens: int) -> None:
    if split == "holdout":
        trajectories = common.load_holdout()[0]
    else:
        trajectories = common.load_dev_split(pairs_per_category=pairs_per_category)
    by_id = {t["trajectory_id"]: t for t in trajectories}
    merged, judge, record = await rejudge_log(log_path, by_id, budget_usd, max_tokens)
    if judge is None:
        print("nothing to re-judge")
        return
    write_rows(log_path, merged)
    log_path.with_suffix(".rejudged.json").write_text(json.dumps(record, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", help="a run under results/ with results.json and step logs")
    parser.add_argument("--log", help="a bare step log (calibration runs have no results.json)")
    parser.add_argument("--split", choices=["holdout", "dev"], default="dev", help="with --log: which trajectories the log covers")
    parser.add_argument("--pairs-per-category", type=int, default=6, help="with --log and --split dev")
    parser.add_argument("--budget-usd", type=float, default=0.5)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--include-refused", action="store_true", help="also re-ask refused steps (refusals are not billed; this records their request ids)")
    args = parser.parse_args()
    global INCLUDE_REFUSED
    INCLUDE_REFUSED = args.include_refused
    if bool(args.run_id) == bool(args.log):
        parser.error("give exactly one of --run-id or --log")
    if args.run_id:
        asyncio.run(rejudge_run(args.run_id, args.budget_usd, args.max_tokens))
    else:
        asyncio.run(rejudge_bare_log(Path(args.log), args.split, args.pairs_per_category, args.budget_usd, args.max_tokens))


if __name__ == "__main__":
    main()
