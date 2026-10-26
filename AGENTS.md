# driftbench: guide for every session

## What it is

An independent benchmark of AI-agent drift detectors, run by a solo founder as a content engine for the alignment-at-scale idea (see `~/coding/_global/projects/ideas/2026-10-26-alignment-at-scale-competitive-brief.md`, sections 5, 9 and 10). It measures false alarms, recall, timing and cost of detectors that anyone can reach, on labelled trajectories, and publishes the harness with the numbers. It is not a product; the revenue path, if any, follows Artificial Analysis and AV-Comparatives: free public results, paid private evaluations later.

## Where it runs

Locally on the Windows PC, inside `.venv` (real Python 3.13 at `%LOCALAPPDATA%\Programs\Python\Python313`, not the Store stub). Nothing is deployed. Results are committed as JSON and Markdown under `results/`; the per-step judge logs (`results/*/steps-*.jsonl`) are gitignored because they repeat the data set.

## Files

- `driftbench/common.py`: paths, `.env` loading, held-out and development-split loaders, prompt versions.
- `driftbench/judge.py`: `OpenRouterJudge`, StepShield's step-judge recipe over OpenRouter with per-step logging, OpenRouter pricing and a hard budget stop.
- `driftbench/run.py`: the runner. `python -m driftbench.run --split holdout --detectors static,constraint,judge --models ... --budget-usd N`.
- `driftbench/metrics_ci.py`: Wilson intervals, bootstrap gap intervals, cross-detector agreement, Markdown summary.
- `driftbench/calibrate.py`: the usage loop (below).
- `prompts/v1.md`: the paper's prompt, pre-registered. `prompts/current.txt` points at the adopted version.
- `docs/PRE-REGISTRATION.md`: question, detectors, decision rules and budget, written before the first paid run.
- `scripts/estimate.py`: token volume and cost per model for both splits (`PYTHONPATH=. python scripts/estimate.py`).
- `vendor/stepshield`: a shallow clone, gitignored, pinned by commit in each `results.json` (`stepshield_commit`). Re-clone with `git clone --depth 1 https://github.com/glo26/stepshield.git vendor/stepshield`.

## Run it locally

```bash
"$LOCALAPPDATA/Programs/Python/Python313/python.exe" -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
git clone --depth 1 https://github.com/glo26/stepshield.git vendor/stepshield
.venv/Scripts/python.exe -m driftbench.run --split holdout --detectors static,constraint
```

Judges need `OPENROUTER_API_KEY` in `.env` (gitignored) or the environment. The key is the owner's; it is never printed, committed or pasted into chat. Every judge run prints its cost estimate first and refuses if it is above `--budget-usd`; during the run it stops at 150% of the estimate.

## Conventions

- Vendor code is never edited; everything is subclassed or wrapped.
- Headline held-out numbers use prompt v1 only. A held-out run with another prompt is labelled with its version and never replaces the headline row.
- Every published number carries an interval. No single-number ranking.
- Vendors get a right of reply before anything is published; AWS and Google terms require disclosing replication details, which the committed harness and `results.json` provide.
- Secrets live only in `.env` or host variables.

## The usage loop (improve with use)

Signals: every judge decision is logged per step with the label. `python -m driftbench.calibrate --model <judge> --budget-usd 2` builds a digest of false alarms, missed rogue steps and premature alerts on the development split (10 training pairs per category, 120 trajectories, chosen by a stable hash, never the held-out set), asks a reviser model for a revised system prompt, saves it as `prompts/vN.md` with provenance, evaluates it with the same judge on the same split, and adopts it only if the false-positive rate drops by at least 2 points while recall drops by less than 2 points and the early-intervention rate by less than 0.05. Each decision is appended to `calibration/log.jsonl` with both metric sets and the cost; `--rollback` restores the previous version. What gets better: the judge's false-alarm rate on fresh trajectories; how it is checked: the next held-out run with the adopted prompt, reported beside the v1 row. Status as of October 26, 2026: mechanism built and import-tested; it has not yet run, because no model key was available in this environment (see history).

## Gotchas

- Training records have `observation: null` on some steps; always use `(step.get("observation") or "")`.
- The paper's LLMJudge judges each step alone (no history window, despite the README's "5-step context" line); `OpenRouterJudge` keeps that, and judges steps concurrently for speed.
- `agent-governance-toolkit` and `invariant-ai` install but ship no default policy that judges a trajectory; running them means writing rules, which measures our rules. The pilot reports them as "no default policy".
- OpenRouter prices are hard-coded in `judge.py` with their date; refresh them from `openrouter.ai/api/v1/models` before a new run.
- Token estimates use tiktoken's o200k encoding. Anthropic models bill about 1.75x that count on this data and write about 150 output tokens a step; OpenAI models match the count and write about 55. `PROVIDER_FACTORS` in `judge.py` holds the measured factors; Google's is a guess until measured. The first Haiku run hit its 150% stop because of this, and `python -m driftbench.repair --run-id <id>` re-judged the 33 unfinished trajectories.
- A run's step log is the source of truth for what was judged; a trajectory with fewer logged steps than it has is unfinished, and `repair.py` finds those.
