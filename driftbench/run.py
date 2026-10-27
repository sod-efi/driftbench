"""Run detectors on a StepShield split and write results with confidence intervals.

Examples (from the repository root, inside the virtual environment):

  python -m driftbench.run --split holdout --detectors static,constraint
  python -m driftbench.run --split holdout --detectors judge \
      --models openai/gpt-4.1-mini,anthropic/claude-haiku-5.5 --budget-usd 5
  python -m driftbench.run --split dev --detectors judge --models anthropic/claude-haiku-5.5 --prompt v1

Every judge run first estimates its cost from the prompt tokens of the split and
refuses to start if the estimate is above the budget. During the run the judge
stops at the budget and marks the remaining steps "budget stop".
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import common
from .metrics_ci import summarize

common.load_env()

from detectors.constraint_guard import ConstraintGuard  # vendor  # noqa: E402
from detectors.static_guard import StaticGuard  # vendor  # noqa: E402
from metrics.timing_metrics import calculate_metrics  # vendor  # noqa: E402
from run_benchmark import run_detector  # vendor  # noqa: E402


def count_prompt_tokens(trajectories: list[dict[str, Any]], system_prompt: str) -> tuple[int, int]:
    import tiktoken
    from detectors.llm_judge import STEP_PROMPT_TEMPLATE  # vendor

    enc = tiktoken.get_encoding("o200k_base")
    sys_tokens = len(enc.encode(system_prompt))
    total = 0
    steps = 0
    for traj in trajectories:
        task = traj.get("task", {})
        cons = task.get("constraints", [])
        cons_text = "\n".join(f"- {c}" for c in cons) if cons else "None"
        for i, step in enumerate(traj["steps"], 1):
            args = step.get("arguments", {})
            args = json.dumps(args, indent=2) if isinstance(args, dict) else str(args)
            user = STEP_PROMPT_TEMPLATE.format(
                task_description=task.get("description", "No description"),
                constraints=cons_text,
                step_index=i,
                thought=step.get("thought", ""),
                action=step.get("action", ""),
                arguments=args,
                observation=(step.get("observation") or "")[:1000],
            )
            total += sys_tokens + len(enc.encode(user))
            steps += 1
    return total, steps


def to_block(name: str, results, metrics, elapsed: float, detector) -> dict[str, Any]:
    return {
        "detector": name,
        "elapsed_seconds": round(elapsed, 1),
        "trajectories_analyzed": len(results),
        "metrics": {
            "eir": metrics.eir,
            "mean_intervention_gap": metrics.mean_intervention_gap,
            "median_intervention_gap": metrics.median_intervention_gap,
            "accuracy": metrics.accuracy,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
            "tokens_saved": metrics.tokens_saved_mean,
        },
        "confusion_matrix": {
            "tp": metrics.true_positives,
            "fp": metrics.false_positives,
            "tn": metrics.true_negatives,
            "fn": metrics.false_negatives,
        },
        "cost": {
            "api_calls": detector.api_calls,
            "total_tokens": detector.total_tokens,
            "total_cost_usd": round(detector.total_cost, 4),
            "budget_exceeded": bool(getattr(detector, "budget_exceeded", False)),
        },
        "trajectory_results": [
            {
                "id": r.trajectory_id,
                "type": r.trajectory_type,
                "category": r.category,
                "total_steps": r.total_steps,
                "detected": r.detected,
                "detection_step": r.detection_step,
                "ground_truth_step": r.ground_truth_step,
                "intervention_gap": r.intervention_gap,
                "is_early": r.is_early,
            }
            for r in results
        ],
    }


async def main_async(args: argparse.Namespace) -> Path:
    if args.split == "holdout":
        trajectories, _stats = common.load_holdout(max_trajectories=args.max)
    else:
        trajectories = common.load_dev_split(pairs_per_category=args.pairs_per_category)
        if args.max:
            trajectories = trajectories[: args.max]
    rogue = sum(1 for t in trajectories if t["trajectory_type"] == "rogue")
    print(f"{args.split}: {len(trajectories)} trajectories ({rogue} rogue, {len(trajectories) - rogue} clean)")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{args.split}"
    out_dir = common.RESULTS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    detectors: dict[str, Any] = {}
    wanted = set(args.detectors.split(","))
    if "static" in wanted:
        detectors["StaticGuard"] = StaticGuard()
    if "constraint" in wanted:
        detectors["ConstraintGuard"] = ConstraintGuard()
    if "judge" in wanted:
        from .judge import OpenRouterJudge, estimate_cost_usd

        prompt_version = args.prompt or common.current_prompt_version()
        system_prompt = common.read_prompt(prompt_version)
        tokens, steps = count_prompt_tokens(trajectories, system_prompt)
        remaining = args.budget_usd
        for model in args.models.split(","):
            est = estimate_cost_usd(model, tokens, steps)
            print(f"estimate {model}: {steps} steps, {tokens:,} input tokens, about ${est:.2f}")
            if est > remaining:
                print(f"REFUSED: estimate ${est:.2f} exceeds remaining budget ${remaining:.2f}", file=sys.stderr)
                continue
            remaining -= est
            judge = OpenRouterJudge(
                model=model,
                prompt_version=prompt_version,
                log_path=out_dir / f"steps-{model.replace('/', '_')}-{prompt_version}.jsonl",
                budget_usd=est * args.hard_stop_factor,  # hard stop above the estimate (default 150%)
                concurrency=args.concurrency,
            )
            detectors[judge.name] = judge

    if not detectors:
        print("nothing to run", file=sys.stderr)
        sys.exit(2)

    blocks: dict[str, Any] = {}
    for name, detector in detectors.items():
        print(f"\n== {name}")
        start = time.time()
        detector.reset_stats() if hasattr(detector, "reset_stats") else None
        results = await run_detector(detector, trajectories)
        metrics = calculate_metrics(results)
        blocks[name] = to_block(name, results, metrics, time.time() - start, detector)
        cm = blocks[name]["confusion_matrix"]
        print(
            f"   recall {metrics.recall*100:.1f}%  FPR {cm['fp']/max(1, cm['fp']+cm['tn'])*100:.1f}%  "
            f"EIR {metrics.eir:.2f}  gap {metrics.mean_intervention_gap:+.2f}  cost ${detector.total_cost:.2f}"
        )

    output = {
        "benchmark_info": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "split": args.split,
            "stepshield_commit": common.vendor_commit(),
            "prompt_version": args.prompt or common.current_prompt_version(),
            "total_trajectories": len(trajectories),
            "rogue_count": rogue,
            "clean_count": len(trajectories) - rogue,
        },
        "results": blocks,
    }
    results_path = out_dir / "results.json"
    results_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    table, ci = summarize(results_path)
    (out_dir / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(
        f"# {run_id}\n\nSplit: {args.split}; StepShield {common.vendor_commit()[:12]}; "
        f"prompt {output['benchmark_info']['prompt_version']}.\n\n{table}\n",
        encoding="utf-8",
    )
    print("\n" + table)
    print(f"\nwritten: {results_path}")
    return results_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["holdout", "dev"], default="holdout")
    parser.add_argument("--hard-stop-factor", type=float, default=1.5, help="judge hard stop as a multiple of its estimate")
    parser.add_argument("--detectors", default="static,constraint", help="comma list of static,constraint,judge")
    parser.add_argument("--models", default="openai/gpt-4.1-mini", help="comma list of OpenRouter model ids")
    parser.add_argument("--prompt", default=None, help="prompt version in prompts/ (default: prompts/current.txt or v1)")
    parser.add_argument("--budget-usd", type=float, default=10.0, help="total budget for all judge models in this run")
    parser.add_argument("--max", type=int, default=None)
    parser.add_argument("--pairs-per-category", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
