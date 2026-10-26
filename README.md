# driftbench

An independent benchmark of AI agent drift detectors: the tools that are supposed to notice when an agent stops doing what it was told.

Vendors sell "goal drift" and "intent" detection for AI agents behind sales calls, and nobody compares them. driftbench runs the detectors anyone can reach (open-source rule engines, cloud guardrail APIs, and plain LLM judges on several models) against trajectories where the exact step the agent went rogue is labelled, and publishes, with confidence intervals and the full harness:

- how often each detector raises a false alarm on a clean run,
- how often it catches a rogue run,
- whether it fires in time (within three steps after the violation, not before it),
- and what it costs per 1,000 trajectories.

The first data set is [StepShield](https://github.com/glo26/stepshield) (Felicia et al., NeurIPS 2026): 216 strictly held-out code-agent trajectories, 108 rogue with the divergence step marked by annotators (kappa 0.82) and 108 clean.

## Pilot results (October 26, 2026, held-out set, prompt v1)

| Detector | False positives on clean | Recall on rogue | Early intervention (k=3) | Premature alerts | Mean gap (steps) | Cost for 216 |
|---|---|---|---|---|---|---|
| StaticGuard (847 rules) | 77.8% [69.1, 84.6] | 86.1% [78.3, 91.4] | 22.6% [15.3, 32.1] | 76.3% | -5.04 [-5.97, -4.13] | US$0 |
| ConstraintGuard | 25.0% [17.8, 33.9] | 24.1% [17.0, 32.9] | 7.7% [2.1, 24.1] | 88.5% | -5.35 [-6.92, -3.62] | US$0 |
| LLM judge, GPT-4.1-mini | 5.6% [2.6, 11.6] | 96.3% [90.9, 98.6] | 91.3% [84.4, 95.4] | 8.7% | -0.42 [-0.78, -0.12] | US$0.75 |
| LLM judge, Claude Haiku 5.5 | 0.0% [0.0, 3.4] | 81.5% [73.1, 87.7] | 100% [95.8, 100] | 0.0% | +0.00 | US$0.42 |

Brackets are 95% Wilson intervals; the gap carries a bootstrap interval. A negative gap means the detector fired before the violation began.

What the first run says:

- **The paper replicates.** GPT-4.1-mini with the paper's prompt lands on 96.3% recall, 5.6% false positives and EIR 0.91, against the paper's 95.4%, 5.6% and 0.89.
- **The judge model sets the operating point.** The same prompt makes Haiku a conservative detector (no false alarms, no premature alerts, every catch exactly on the divergence step) and GPT-4.1-mini an eager one (catches 15 points more, fires early on 8.7% of rogue runs, false alarms on 5.6% of clean ones). The two recall intervals do not overlap. Vendors who sell "an LLM-based monitor" without naming the model are selling an unknown operating point.
- **Where Haiku misses.** 20 rogue runs, 16 of which GPT-4.1-mini caught: destructive actions (recall 61%) and resource hijacking (56%), while exfiltration, privilege escalation and persistence sit at 89 to 94%. Misses grow with subtlety: 4 of 36 obvious (L1), 6 of 36 clear (L2), 10 of 36 subtle (L3) cases.
- **Rules are not detectors.** Three quarters of StaticGuard's alerts on rogue runs fire before anything went wrong.

The two judges agree on 89.8% of trajectories (kappa 0.80); of the 88 rogue runs both caught, 80 were flagged at the same step.

Not yet run: Claude Sonnet 5.5 (about US$8.70), Claude Opus 5.5 (about US$17), Gemini 3.5 Flash Lite (about US$1), the full development-split calibration, and anything from the sales-gated vendors. See `docs/PROJECT_HISTORY.md`.

## How it improves with use

Every judge decision is logged. `python -m driftbench.calibrate` turns the mistakes on a development split (never the held-out set) into a revised prompt, tests it against the current one with the same judge, and adopts it only under a rule fixed in advance. Every version is kept and every adoption can be rolled back. The first cycle ran on October 26 and kept v1 (details in the history). Details of the mechanism in `AGENTS.md`.

## Licences

Harness: MIT. StepShield code is MIT and its data CC BY 4.0 (credit: Felicia, Sasindran, He, Eniolade, Kumar, Angati, 2026); it is pulled into `vendor/` and never modified.
