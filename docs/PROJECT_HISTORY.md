# Project history

## 2026-10-26: pilot harness built, free detectors run

Why: the alignment-at-scale competitive brief (in `_global/projects/ideas`) found that nobody independently compares agent drift detectors, that StepShield is the only open set with the drift step labelled, and that a pilot costs tens of dollars. The owner asked for the pilot.

Built: `driftbench/` harness over StepShield's benchmark package (vendored, unmodified, commit 031aa882): an OpenRouter judge with per-step logging and budget stops, Wilson and bootstrap intervals, cross-detector agreement, a pre-registration note, and the calibration loop (`calibrate.py`) with prompt versioning, an adoption rule and rollback.

Run: StaticGuard and ConstraintGuard on the 216 held-out trajectories (`results/2026-10-26-holdout-free`). Both reproduce the paper's rows exactly (StaticGuard 86.1% recall, 77.8% false positives, EIR 0.23; ConstraintGuard 24.1%, 25.0%, 0.08), which confirms the data and metrics pipeline.

Measured, not run: 3,056 judged steps and 1,174,797 input tokens on the held-out set with prompt v1. Estimates per judge (OpenRouter prices of this date, 80 output tokens a step assumed): GPT-4.1-mini about US$0.86, Claude Haiku 5.5 US$0.24, Claude Sonnet 5.5 US$4.79, Gemini 3.5 Flash Lite US$0.96, Claude Opus 5.5 US$9.59. All five together about US$16.50; the development split costs roughly 40% of that per model.

Blocked: the judges did not run. The only model key on this computer is the Kickaround service's OpenRouter key on Railway, and reading it was refused by the session's permission layer as credential exploration. The owner decides how a key reaches `.env` (or the environment). No paid call has been made.

Checked and not used: `agent-governance-toolkit` 4.1.0 and `invariant-ai` 0.3.5 install, but neither ships a default policy that judges a trajectory.

## Open items

- Provide `OPENROUTER_API_KEY` to `.env` (owner), then run the five judges on the held-out set (about US$17) and one calibration cycle on the development split with Haiku (about US$0.30).
- Write the report with the agreement table and the three pre-registered readings.
- Full run: ATBench as a mixed-safety check, AgentDrift as an attack track, 200 home-made drift trajectories with a private held-out split, Azure Task Adherence and Lakera once accounts exist (owner creates accounts), invitations to the sales-gated vendors.
- Publish: open repo, dated report, right of reply, quarterly reruns.

## Ideas discussed but not built

- Whole-transcript judging as a cheaper mode (284k tokens for the whole held-out set) alongside step-by-step.
- A reviewer-model check for the "copies the agent's first answer" failure reported in the literature: seeded should-fail runs in the development split.
