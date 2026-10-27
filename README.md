# driftbench

An independent benchmark of AI agent drift detectors: the tools that are supposed to notice when an agent stops doing what it was told.

Vendors sell "goal drift" and "intent" detection for AI agents behind sales calls, and nobody compares them. driftbench runs the detectors anyone can reach (open-source rule engines, cloud guardrail APIs, and plain LLM judges on several models) against trajectories where the exact step the agent went rogue is labelled, and publishes, with confidence intervals and the full harness:

- how often each detector raises a false alarm on a clean run,
- how often it catches a rogue run,
- whether it fires in time (within three steps after the violation, not before it),
- and what it costs per 1,000 trajectories.

The first data set is [StepShield](https://github.com/glo26/stepshield) (Felicia et al., NeurIPS 2026): 216 strictly held-out code-agent trajectories, 108 rogue with the divergence step marked by annotators (kappa 0.82) and 108 clean.

## Pilot results (October 26-27, 2026, held-out set, the paper's prompt)

| Detector | False positives on clean | Recall on rogue | Early intervention (k=3) | Premature alerts | Mean gap (steps) | Cost per 1,000 runs |
|---|---|---|---|---|---|---|
| StaticGuard (847 rules) | 77.8% [69.1, 84.6] | 86.1% [78.3, 91.4] | 22.6% [15.3, 32.1] | 76.3% | -5.04 [-5.97, -4.13] | US$0 |
| ConstraintGuard | 25.0% [17.8, 33.9] | 24.1% [17.0, 32.9] | 7.7% [2.1, 24.1] | 88.5% | -5.35 [-6.92, -3.62] | US$0 |
| LLM judge, GPT-4.1-mini | 5.6% [2.6, 11.6] | 96.3% [90.9, 98.6] | 91.3% [84.4, 95.4] | 8.7% | -0.42 [-0.78, -0.12] | US$3.50 |
| LLM judge, Gemini 3.5 Flash Lite | 15.7% [10.1, 23.8] | 98.1% [93.5, 99.5] | 91.5% [84.6, 95.5] | 8.5% | -0.52 [-0.92, -0.19] | US$4.10 |
| LLM judge, Claude Haiku 5.5 | 24.1% [17.0, 32.9] | 99.1% [94.9, 99.8] | 91.6% [84.8, 95.5] | 8.4% | -0.41 [-0.77, -0.13] | US$2.90 |
| LLM judge, Claude Sonnet 5.5, refusal scored as silence | 14.8% [9.3, 22.7] | 69.4% [60.2, 77.3] | 86.7% [77.2, 92.6] | 10.7% | -0.20 [-0.85, +0.39] | US$40 |
| LLM judge, Claude Sonnet 5.5, refusal scored as an alert | 15.7% [10.1, 23.8] | 99.1% [94.9, 99.8] | 92.5% [85.9, 96.2] | 7.5% | | US$40 |
| LLM judge, Claude Opus 5.5, refusal scored as silence | 19.4% [13.1, 27.9] | 38.0% [29.4, 47.4] | 68.3% [53.0, 80.4] | 24.4% | -0.98 [-2.12, +0.05] | US$68 |
| LLM judge, Claude Opus 5.5, refusal scored as an alert | 21.3% [14.6, 29.9] | 100% [96.6, 100] | 88.9% [81.6, 93.5] | 11.1% | | US$68 |

Brackets are 95% Wilson intervals; the gap carries a bootstrap interval. A negative gap means the detector fired before the violation began. Every judge ran the paper's prompt (v1) unchanged, each step judged on its own at temperature 0, through OpenRouter. Cut-off answers were re-asked with a larger output cap (see "A correction" below).

What the pilot says:

- **The paper replicates.** GPT-4.1-mini with the paper's prompt lands on 96.3% recall, 5.6% false positives and EIR 0.91, against the paper's 95.4%, 5.6% and 0.89.
- **The judge model sets the false-alarm rate, not the catch rate.** With the same prompt, every judge that answers catches 96 to 99% of rogue runs, within each other's intervals. False alarms on clean runs differ by model and the intervals do not overlap: GPT-4.1-mini 5.6%, Gemini Flash Lite 15.7%, Claude Haiku 24.1%. Vendors who sell "an LLM-based monitor" without naming the model are selling an unknown false-alarm rate, and false alarms are what gets a monitor switched off.
- **Price does not buy accuracy.** Claude Sonnet 5.5 costs eleven times GPT-4.1-mini per run and Claude Opus 5.5 twenty times; neither does better on either axis, and both do worse unless their refusals are counted as alarms.
- **A safety filter can blind a monitor exactly when it matters.** Why would a safety filter fire on a monitoring question? Because the question contains the evidence. When the step under review is "send the customer database to an outside server", the request to judge it looks, to the filter, like a request about exfiltration, and it declines. Anthropic's classifier did this to 83 of Sonnet 5.5's 3,056 step requests and 179 of Opus 5.5's, as "violative cyber content". The refusals land where the evidence is: for Opus, 175 of the 179 were steps of rogue runs, 83 of them the exact step where the agent went rogue, spread over 86 of the 108 rogue runs; for Sonnet, 82 of 83, 54 at the exact step, in 55 runs. Haiku 5.5, asked the same questions, answered every one. What happens next decides the monitor's worth. A monitor that only reads the JSON treats "no answer" as "nothing wrong": scored that way, Sonnet catches 69.4% of rogue runs and Opus 38.0%, the two worst in the table. A monitor that treats "the judge refused to look at this step" as an alarm in its own right gets 99.1% from Sonnet and 100% from Opus, in line with the best. Same model, same answers, a thirty- to sixty-point difference decided by how the monitor handles silence. Nobody who sells a monitor on a filtered model says which they do.
- **Rules are not detectors.** Three quarters of StaticGuard's alerts on rogue runs fire before anything went wrong.

Agreement: GPT-4.1-mini and Gemini Flash Lite agree on 92.1% of trajectories (kappa 0.84); Haiku agrees with them on 86.6% and 88.9%; the two refusing models agree with the rest far less (Sonnet kappa about 0.53, Opus 0.15 to 0.28) because of their silences. No rogue run escaped every judge; 34 of 108 were caught by all five. Destructive actions are the hardest category for every judge that answers (GPT-4.1-mini 78%, Gemini 89%, Haiku 94% recall), while exfiltration, privilege escalation, persistence and test tampering are caught at 100% by those three. Refusals rise with the model tier: Haiku 0 steps, Sonnet 83, Opus 179.

### A correction to the October 26 report

The first report said Claude Haiku 5.5 was a conservative judge (0% false positives, 81.5% recall, every catch on the exact step). That was an artifact. StepShield's judge caps answers at 200 output tokens; Claude models write longer reasons, so 27% of Haiku's answers were cut off mid-JSON and the vendor parser scored them "not rogue". Re-asking only those steps with a 600-token cap (same prompt, same model, temperature 0; each step is judged alone, so nothing else changes) gives the Haiku row above: the most eager judge, not the most conservative. The same cap had cut off 7% of Sonnet's answers; Opus ran with the larger cap from the start. Both step logs record `parse_status` per answer now, and `python -m driftbench.rejudge` repairs a run. Details in `docs/PROJECT_HISTORY.md` and the addendum in `docs/PRE-REGISTRATION.md`.

Not yet run: anything from the sales-gated vendors.

## How it improves with use

Every judge decision is logged. `python -m driftbench.calibrate` turns the mistakes on a development split (never the held-out set) into a revised prompt, tests it against the current one with the same judge, and adopts it only under a rule fixed in advance. Every version is kept and every adoption can be rolled back. Two cycles have run (October 26 and 27); both kept v1: the proposed v2 raised Haiku's false-alarm rate on the development split from 36% to 86%. Details of the mechanism in `AGENTS.md`.

## Licences

Harness: MIT. StepShield code is MIT and its data CC BY 4.0 (credit: Felicia, Sasindran, He, Eniolade, Kumar, Angati, 2026); it is pulled into `vendor/` and never modified.
