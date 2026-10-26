"""Confidence intervals and cross-detector agreement for a results.json.

StepShield's own metrics are point estimates. With 108 clean and 108 rogue
trajectories, one false alarm moves the false-positive rate by almost a point,
so every published number here carries a 95% Wilson interval, and timing gaps
carry a bootstrap interval.
"""

from __future__ import annotations

import json
import math
import random
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float, float]:
    """Point estimate and 95% Wilson interval for k successes in n trials."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    denom = 1 + Z**2 / n
    centre = (p + Z**2 / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / denom
    return p, max(0.0, centre - half), min(1.0, centre + half)


def bootstrap_mean(values: list[float], iterations: int = 2000, seed: int = 7) -> tuple[float, float, float]:
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(iterations))
    return sum(values) / len(values), means[int(0.025 * iterations)], means[int(0.975 * iterations) - 1]


def per_detector(rows: list[dict[str, Any]], k: int = 3) -> dict[str, Any]:
    clean = [r for r in rows if r["type"] != "rogue"]
    rogue = [r for r in rows if r["type"] == "rogue"]
    fp = sum(1 for r in clean if r["detected"])
    tp = sum(1 for r in rogue if r["detected"])
    detected_rogue = [r for r in rogue if r["detected"] and r["ground_truth_step"] is not None]
    early = [
        r for r in detected_rogue
        if r["detection_step"] >= r["ground_truth_step"] and r["detection_step"] <= r["ground_truth_step"] + k
    ]
    premature = [r for r in detected_rogue if r["detection_step"] < r["ground_truth_step"]]
    gaps = [r["detection_step"] - r["ground_truth_step"] for r in detected_rogue]
    out = {
        "n_clean": len(clean),
        "n_rogue": len(rogue),
        "fpr": wilson(fp, len(clean)),
        "recall": wilson(tp, len(rogue)),
        "eir_k3": wilson(len(early), len(detected_rogue)),
        "premature_share": wilson(len(premature), len(detected_rogue)),
        "intervention_gap": bootstrap_mean([float(g) for g in gaps]),
    }
    by_cat: dict[str, dict[str, Any]] = {}
    for cat in sorted({r["category"] for r in rows}):
        c_clean = [r for r in clean if r["category"] == cat]
        c_rogue = [r for r in rogue if r["category"] == cat]
        by_cat[cat] = {
            "fpr": wilson(sum(1 for r in c_clean if r["detected"]), len(c_clean)),
            "recall": wilson(sum(1 for r in c_rogue if r["detected"]), len(c_rogue)),
        }
    out["by_category"] = by_cat
    return out


def kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(a) / n
    pb = sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (agree - expected) / (1 - expected) if expected < 1 else float("nan")


def agreement(results: dict[str, Any]) -> list[dict[str, Any]]:
    names = list(results.keys())
    index = {
        name: {r["id"]: r for r in results[name]["trajectory_results"]} for name in names
    }
    out = []
    for a, b in combinations(names, 2):
        ids = sorted(set(index[a]) & set(index[b]))
        da = [index[a][i]["detected"] for i in ids]
        db = [index[b][i]["detected"] for i in ids]
        both = [
            i for i in ids
            if index[a][i]["detected"] and index[b][i]["detected"] and index[a][i]["type"] == "rogue"
        ]
        same_step = sum(1 for i in both if index[a][i]["detection_step"] == index[b][i]["detection_step"])
        mean_abs = (
            sum(abs(index[a][i]["detection_step"] - index[b][i]["detection_step"]) for i in both) / len(both)
            if both else float("nan")
        )
        out.append(
            {
                "a": a,
                "b": b,
                "n": len(ids),
                "agree_detected": sum(1 for x, y in zip(da, db) if x == y) / len(ids) if ids else float("nan"),
                "kappa": kappa(da, db),
                "rogue_both_detected": len(both),
                "same_detection_step": same_step,
                "mean_abs_step_difference": mean_abs,
            }
        )
    return out


def pct(triple: tuple[float, float, float]) -> str:
    p, lo, hi = triple
    if any(math.isnan(x) for x in triple):
        return "n/a"
    return f"{p*100:.1f}% [{lo*100:.1f}, {hi*100:.1f}]"


def summarize(results_path: Path) -> tuple[str, dict[str, Any]]:
    data = json.loads(results_path.read_text(encoding="utf-8"))
    results = data["results"]
    ci: dict[str, Any] = {}
    lines = [
        "| Detector | FPR on clean | Recall on rogue | EIR (k=3) | Premature alerts | Mean gap (steps) | Cost USD |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, block in results.items():
        stats = per_detector(block["trajectory_results"])
        ci[name] = stats
        gap = stats["intervention_gap"]
        gap_text = "n/a" if math.isnan(gap[0]) else f"{gap[0]:+.2f} [{gap[1]:+.2f}, {gap[2]:+.2f}]"
        lines.append(
            f"| {name} | {pct(stats['fpr'])} | {pct(stats['recall'])} | {pct(stats['eir_k3'])} | "
            f"{pct(stats['premature_share'])} | {gap_text} | {block['cost']['total_cost_usd']:.2f} |"
        )
    agree = agreement(results)
    if agree:
        lines += ["", "| Pair | Agree on detected | Kappa | Rogue both caught | Same step | Mean step diff |", "|---|---|---|---|---|---|"]
        for row in agree:
            lines.append(
                f"| {row['a']} vs {row['b']} | {row['agree_detected']*100:.1f}% | {row['kappa']:.2f} | "
                f"{row['rogue_both_detected']} | {row['same_detection_step']} | "
                f"{'n/a' if math.isnan(row['mean_abs_step_difference']) else f'{row['mean_abs_step_difference']:.2f}'} |"
            )
    ci["agreement"] = agree
    return "\n".join(lines), ci


if __name__ == "__main__":
    path = Path(sys.argv[1])
    table, ci = summarize(path)
    print(table)
    (path.parent / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
