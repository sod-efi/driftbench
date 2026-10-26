# driftbench

An independent benchmark of AI agent drift detectors: the tools that are supposed to notice when an agent stops doing what it was told.

Vendors sell "goal drift" and "intent" detection for AI agents behind sales calls, and nobody compares them. driftbench runs the detectors anyone can reach (open-source rule engines, cloud guardrail APIs, and plain LLM judges on several models) against trajectories where the exact step the agent went rogue is labelled, and publishes, with confidence intervals and the full harness:

- how often each detector raises a false alarm on a clean run,
- how often it catches a rogue run,
- whether it fires in time (within three steps after the violation, not before it),
- and what it costs per 1,000 trajectories.

The first data set is [StepShield](https://github.com/glo26/stepshield) (Felicia et al., NeurIPS 2026): 216 strictly held-out code-agent trajectories, 108 rogue with the divergence step marked by annotators (kappa 0.82) and 108 clean.

## Pilot results so far (October 26, 2026)

Free detectors on the held-out set, reproducing the paper's rows exactly:

| Detector | False positives on clean | Recall on rogue | Early intervention (k=3) | Mean gap (steps) |
|---|---|---|---|---|
| StaticGuard (847 rules) | 77.8% [69.1, 84.6] | 86.1% [78.3, 91.4] | 22.6% [15.3, 32.1] | -5.04 [-5.97, -4.13] |
| ConstraintGuard | 25.0% [17.8, 33.9] | 24.1% [17.0, 32.9] | 7.7% [2.1, 24.1] | -5.35 [-6.92, -3.62] |

Brackets are 95% intervals. A negative gap means the detector fired before the violation began: three quarters of StaticGuard's alerts on rogue runs are premature.

LLM judges (GPT-4.1-mini, Claude Haiku 5.5, Claude Sonnet 5.5, Gemini 3.5 Flash Lite, Claude Opus 5.5) are set up and costed but not yet run: see `docs/PROJECT_HISTORY.md`.

## How it improves with use

Every judge decision is logged. `python -m driftbench.calibrate` turns the mistakes on a development split (never the held-out set) into a revised prompt, tests it against the current one with the same judge, and adopts it only under a rule fixed in advance. Every version is kept and every adoption can be rolled back. Details in `AGENTS.md`.

## Licences

Harness: MIT. StepShield code is MIT and its data CC BY 4.0 (credit: Felicia, Sasindran, He, Eniolade, Kumar, Angati, 2026); it is pulled into `vendor/` and never modified.
