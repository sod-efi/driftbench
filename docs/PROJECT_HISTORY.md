# Project history

## 2026-10-26 (night): judges run, paper replicated, first calibration cycle

Why: the owner authorized reading Kickaround's OpenRouter key into `.env` through a pipe, then asked to keep the spend small so Kickaround's users keep their credit. The account had US$7.49 left, so the run was cut to the two cheapest judges and one small calibration cycle, about US$1.60 in all.

Ran (`results/2026-10-26-holdout-judges`): Claude Haiku 5.5 and GPT-4.1-mini with prompt v1 on all 216 held-out trajectories. GPT-4.1-mini replicates the paper (96.3% recall, 5.6% FPR, EIR 0.91 against 95.4%, 5.6%, 0.89). Haiku is a different operating point: 0% FPR, 81.5% recall, every catch on the exact divergence step. Full table and reading in `README.md`.

Lesson and fix: the pre-run estimate counted tokens with tiktoken's o200k encoding; Anthropic bills about 1.75x that on this data and Haiku writes about 150 output tokens a step, so Haiku hit its 150% hard stop at step 2,615 of 3,056. `driftbench/repair.py` re-judged the 33 unfinished trajectories for US$0.06 (same prompt, same model, temperature 0, so the merge is clean), and `PROVIDER_FACTORS` in `judge.py` now carries the measured factors. Corrected estimates for the full held-out set: Sonnet 5.5 about US$8.70, Opus 5.5 about US$17, not the US$4.79 and US$9.59 written earlier. Also fixed: a judge answering `"confidence": "high"` crashed the logger; `as_confidence()` now coerces words and junk.

Calibration (`results/20261026-231621-calibrate` and the resumed run that followed): development split of 6 training pairs per category (72 trajectories, 866 steps). Haiku with v1: FPR 8.3%, recall 33.3%, EIR 0.58, US$0.12. Digest: 3 false alarms, 28 missed rogue steps, 3 premature alerts. Sonnet 5.5 proposed v2 (the first proposal was cut off at 1,500 output tokens and discarded; the limit is now 3,500 with a check on the finish reason). v2 evaluated with Haiku until the per-evaluation budget stop at US$0.21: FPR 11.1%, recall 63.9%, EIR 0.78 on the trajectories it reached. The rule kept v1: the comparison was incomplete, and v2's false-positive rate rose rather than fell, so it would have been rejected anyway. `prompts/current.txt` stays v1; `calibration/log.jsonl` holds the entry. The mechanism ran end to end (log, digest, proposal, evaluation, rule, log, pointer); it has not yet produced an adopted improvement, so nothing is claimed as "measured improvement".

Unexplained, to investigate: Haiku's recall on the training-pair development split (33%) is far below its held-out recall (81.5%). Training records differ from held-out ones (in-record labels, some null observations, possibly subtler step framing); the digest shows the misses are mostly resource-hijacking and destructive-action steps whose rogue nature depends on the task's stated limits, which v1's prompt never mentions and v2's does.

Spend this night, from the result files: smoke test US$0.01, Haiku US$0.42, GPT-4.1-mini US$0.75, calibration US$0.33 plus two reviser calls about US$0.07; about US$1.59 in all (OpenRouter credits page: US$29.11 used of US$35, so US$5.89 left for Kickaround, checked 2026-10-26 night).

## 2026-10-26 (day): pilot harness built, free detectors run

Why: the alignment-at-scale competitive brief (in `_global/projects/ideas`) found that nobody independently compares agent drift detectors, that StepShield is the only open set with the drift step labelled, and that a pilot costs tens of dollars. The owner asked for the pilot.

Built: `driftbench/` harness over StepShield's benchmark package (vendored, unmodified, commit 031aa882): an OpenRouter judge with per-step logging and budget stops, Wilson and bootstrap intervals, cross-detector agreement, a pre-registration note, and the calibration loop (`calibrate.py`) with prompt versioning, an adoption rule and rollback.

Run: StaticGuard and ConstraintGuard on the 216 held-out trajectories (`results/2026-10-26-holdout-free`). Both reproduce the paper's rows exactly (StaticGuard 86.1% recall, 77.8% false positives, EIR 0.23; ConstraintGuard 24.1%, 25.0%, 0.08), which confirms the data and metrics pipeline.

Checked and not used: `agent-governance-toolkit` 4.1.0 (imports as `agent_compliance`: red-team, prompt-defence and policy-lint tools) and `invariant-ai` 0.3.5 (a rule engine) install, but neither ships a default policy that judges a trajectory.

## Open items

- After a top-up: finish the v2 evaluation on the development split (`python -m driftbench.repair` does not yet cover calibration runs; either add that or rerun `calibrate --from-run <run> --candidate v2` with `--budget-usd 0.6`), then Gemini 3.5 Flash Lite (about US$1) and Sonnet 5.5 (about US$8.70) on the held-out set.
- Investigate the development-split gap (33% recall) before trusting calibration deltas; consider calibrating on StepShield's deployment-test split instead.
- Write the report with the agreement table and the three pre-registered readings; invite the sales-gated vendors; right of reply.
- Full run: ATBench as a mixed-safety check, AgentDrift as an attack track, 200 home-made drift trajectories with a private held-out split, Azure Task Adherence and Lakera once accounts exist (owner creates accounts).
- Publish: open repo, dated report, quarterly reruns.

## Ideas discussed but not built

- Whole-transcript judging as a cheaper mode (284k tokens for the whole held-out set) alongside step-by-step.
- A reviewer-model check for the "copies the agent's first answer" failure reported in the literature: seeded should-fail runs in the development split.
- Per-step concurrency across trajectories (the vendor rate limiter makes a 3,056-step run take about 10 minutes per model).
