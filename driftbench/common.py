"""Shared paths, environment and data loading for the driftbench pilot.

The StepShield benchmark code and data live in vendor/stepshield (MIT code,
CC BY 4.0 data, Felicia et al. 2026). This module puts its benchmark package
on sys.path and wraps its loader, so the pilot never edits vendor code.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "stepshield"
BENCH = VENDOR / "benchmark"
DATA = VENDOR / "data"
PROMPTS = ROOT / "prompts"
RESULTS = ROOT / "results"
CALIBRATION = ROOT / "calibration"

if str(BENCH) not in sys.path:
    sys.path.insert(0, str(BENCH))


def load_env() -> None:
    """Load KEY=VALUE lines from .env into os.environ without printing them."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def vendor_commit() -> str:
    head = VENDOR / ".git" / "HEAD"
    if not head.exists():
        return "unknown"
    ref = head.read_text().strip()
    if ref.startswith("ref:"):
        ref_path = VENDOR / ".git" / ref.split(" ", 1)[1]
        return ref_path.read_text().strip() if ref_path.exists() else "unknown"
    return ref


def load_holdout(max_trajectories: int | None = None) -> tuple[list[dict[str, Any]], Any]:
    """The 216-record strictly held-out split, labels from the answer key."""
    from data_loader import load_dataset  # vendor

    return load_dataset(str(DATA / "test_holdout" / "scrubbed"), max_trajectories=max_trajectories)


def load_dev_split(pairs_per_category: int = 10) -> list[dict[str, Any]]:
    """A deterministic sample of labelled training pairs for calibration.

    The held-out split is never used for calibration. Pairs are picked by a
    stable hash of the pair id, so every run sees the same development set.
    """
    out: list[dict[str, Any]] = []
    for cat in ["DEC", "INV", "RES", "SEC", "TST", "UFO"]:
        cat_dir = DATA / "train" / cat
        rogue_files = sorted(cat_dir.glob("*-ROGUE.jsonl"))
        pair_ids = [p.name[: -len("-ROGUE.jsonl")] for p in rogue_files]
        pair_ids.sort(key=lambda pid: hashlib.sha1(pid.encode()).hexdigest())
        for pid in pair_ids[:pairs_per_category]:
            for kind in ("ROGUE", "CLEAN"):
                path = cat_dir / f"{pid}-{kind}.jsonl"
                if not path.exists():
                    continue
                traj = json.loads(path.read_text(encoding="utf-8"))
                traj.setdefault("trajectory_id", path.stem)
                traj["category"] = cat
                traj["trajectory_type"] = "rogue" if kind == "ROGUE" else "correct"
                rogue_step = None
                for step in traj.get("steps", []):
                    if step.get("label"):
                        rogue_step = step["step"]
                        break
                traj["rogue_step"] = rogue_step
                out.append(traj)
    return out


def read_prompt(version: str) -> str:
    path = PROMPTS / f"{version}.md"
    text = path.read_text(encoding="utf-8")
    # Everything after the first '---' line is the prompt body; above it is provenance.
    if "\n---\n" in text:
        return text.split("\n---\n", 1)[1].strip()
    return text.strip()


def current_prompt_version() -> str:
    pointer = PROMPTS / "current.txt"
    return pointer.read_text(encoding="utf-8").strip() if pointer.exists() else "v1"
