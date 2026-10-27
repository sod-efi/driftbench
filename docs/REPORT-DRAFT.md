# Which drift detector actually notices? Five LLM judges and two rule engines on StepShield's held-out set

Draft for the owner's review, October 27, 2026. Not published. Right of reply pending (see the end).

## In one paragraph

Agent "drift" or "intent" monitors are sold behind sales calls and never compared. We took the one public data set where the exact step an agent went rogue is labelled, StepShield's 216 held-out code-agent trajectories, and ran the detectors anyone can reach: StepShield's two rule engines and its own step-by-step LLM-judge recipe on five models through one API. Three things came out. The paper replicates. With the same prompt, the judge model does not change how many rogue runs are caught (96 to 99% for every model that answers) but changes how often a clean run is flagged, from 5.6% to 24.1%, with non-overlapping intervals. And a model's own safety filter can blind the monitor exactly when it matters: Claude Sonnet 5.5 declined to judge 83 steps and Claude Opus 5.5 179, as "violative cyber content"; for Opus, 175 of those were steps of rogue runs and 83 the very step where the agent went rogue, which a monitor that reads only the JSON scores as "nothing happened". Everything here cost US$27 in API calls and reproduces from the committed harness.

## Why this matters

As agents act with less supervision, the question "is it still doing what I told it?" is answered, if at all, by a monitor that watches each step. Vendors describe theirs as "an LLM-based monitor" or "behavioural analysis" and publish no false-alarm rate, no recall, and never the model. A monitor that flags a quarter of clean runs gets switched off; a monitor that goes silent on dangerous steps is worse than none. Both failure modes showed up here with the paper's own recipe, which makes them a property of the approach, not of one vendor.

## Data and method

- **Data.** StepShield (Felicia, Sasindran, He, Eniolade, Kumar and Angati, arXiv 2601.22136, January 2026, revised July 2026; code MIT, data CC BY 4.0), commit 031aa882. 216 strictly held-out trajectories: 108 rogue with the divergence step labelled by annotators (kappa 0.82), 108 clean. Six violation categories: destructive actions (DEC), privilege escalation (INV), resource hijacking (RES), security and exfiltration (SEC), test tampering (TST), unauthorized file operations (UFO); three severity levels.
- **Detectors.** StepShield's StaticGuard (847 regex rules) and ConstraintGuard, run as shipped. StepShield's LLMJudge recipe (each step judged alone, no history window, the paper's system prompt verbatim, temperature 0, JSON answer) run through OpenRouter on GPT-4.1-mini (the paper's model), Gemini 3.5 Flash Lite, Claude Haiku 5.5, Claude Sonnet 5.5 and Claude Opus 5.5.
- **Metrics.** False-positive rate on clean runs; recall on rogue runs; early-intervention rate (alert within three steps after the labelled step and not before it); premature-alert share; mean gap in steps between the alert and the labelled step; cost. 95% Wilson intervals; bootstrap interval on the gap. Pre-registered before the first paid run (`docs/PRE-REGISTRATION.md`), including what would count as a story.
- **One deviation, disclosed.** The paper's recipe caps answers at 200 output tokens. Claude models write longer reasons, and the recipe's parser scores a cut-off answer as "not rogue". The steps that were cut off (836 of 3,056 for Haiku, 216 for Sonnet) were re-asked with a 600-token cap, same prompt, same model, temperature 0. Because each step is judged alone, no other answer is affected. The step logs record a parse status per answer.

## Results

Held-out set, 216 trajectories, the paper's prompt.

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

A negative gap means the detector fired before the violation began.

### 1. The paper replicates

GPT-4.1-mini with the paper's prompt gives 96.3% recall, 5.6% false positives and an early-intervention rate of 0.91, against the paper's 95.4%, 5.6% and 0.89. The two rule engines reproduce the paper's rows exactly, which also confirms the data and metric pipeline.

### 2. The judge model sets the false-alarm rate, not the catch rate

Same prompt, same steps, same temperature. Every judge that answers catches 96 to 99% of rogue runs, within each other's intervals, and fires early on 8 to 9% of them. What differs is what they do with clean runs: GPT-4.1-mini flags 5.6%, Gemini Flash Lite 15.7%, Claude Haiku 24.1%, and the first and last intervals do not touch. The judges agree with each other on 87 to 92% of trajectories (kappa 0.73 to 0.84), so this is one recipe with a model-dependent threshold, not three different detectors. The cheapest OpenAI model is the best operating point in this set; Sonnet at eleven times GPT-4.1-mini's price and Opus at twenty times are no better on either axis, and both are worse unless their refusals count as alarms (section 3).

For a buyer: a vendor that sells "an LLM-based monitor" without naming the model and publishing its clean-run false-alarm rate is selling an unknown nuisance rate, and nuisance is what gets monitors switched off.

### 3. A safety filter can blind the monitor exactly when it matters

Why would a safety filter fire on a monitoring question? Because the question contains the evidence. When the step under review is "send the customer database to an outside server", the request to judge it looks, to the filter, like a request about exfiltration, and it declines. Anthropic's classifiers did this to 83 of Sonnet 5.5's 3,056 step requests and to 179 of Opus 5.5's. The response carries no verdict; through OpenRouter it arrives as finish reason `content_filter` with the text "This request triggered restrictions on violative cyber content and was blocked under Anthropic's Usage Policy". Anthropic's documentation describes this as the "cyber" refusal category, notes that "benign cybersecurity work can also trigger this category", does not bill it, and recommends retrying on another model.

The refusals are not random. For Opus, 175 of the 179 fall on rogue runs (4 on clean runs), 83 of them on the exact step where the agent went rogue, spread over 86 of the 108 rogue runs: 47 unauthorized file operations, 40 exfiltration, 29 test tampering, 26 privilege escalation, 22 resource hijacking, 11 destructive. For Sonnet, 82 of 83 fall on rogue runs, 54 at the exact step, in 55 runs. Haiku 5.5, asked the same question about the same steps, answered every one. The filter is reacting to the evidence of rogue behaviour in the step the monitor was asked to judge, and it reacts more often the more capable the model: Haiku 0 steps, Sonnet 83, Opus 179. Asked a third time, one of Sonnet's original 84 refused steps was answered, so refusals are stable but not perfectly so at temperature 0; every refusal carries its request id in the step log.

What happens next decides what the monitor is worth. The monitor sent a question and got no answer. A monitor that only reads the JSON, as the recipe's parser does, treats "no answer" as "nothing wrong here": scored that way, Sonnet catches 69.4% of rogue runs and Opus 38.0%, the two worst results in the table, and Opus's early-intervention rate drops to 68% because the catches that remain are the late ones. A monitor that treats "the judge refused to look at this step" as an alarm in its own right gets 99.1% recall from Sonnet at 15.7% false alarms and 100% from Opus at 21.3%, in line with the judges that answer. Same model, same answers, a thirty- to sixty-point difference decided entirely by how the monitor handles silence. Nobody who sells a monitor built on a filtered model says which of the two they do, and a vendor's own harness is as likely as the paper's to have scored the silence as safety.

### 4. Rules are not detectors

StaticGuard catches 86% of rogue runs, but three quarters of its alerts fire before anything has gone wrong, and it flags 78% of clean runs. ConstraintGuard flags a quarter of clean runs and catches a quarter of rogue ones.

### Where the judges miss

No rogue run escaped all five judges; 34 of 108 were caught by all five, the number pulled down by the two refusing models. Destructive actions are the hardest category for every judge (GPT-4.1-mini 78%, Gemini 89%, Haiku 94% recall); exfiltration, privilege escalation, persistence and test tampering are caught at 100% by the three judges that answer. Severity barely matters once the model answers (94 to 100% at every level).

## A correction to our own first reading

An earlier internal report (October 26) said Claude Haiku 5.5 was a conservative judge: 0% false positives, 81.5% recall, every catch on the exact step. That was the 200-token cap at work: 27% of Haiku's answers had been cut off and scored "not rogue". The corrected row above is the most eager judge, not the most conservative. We publish this because any harness built on the recipe without a parse-status check will carry the same error, and because it is the kind of mistake a vendor's internal benchmark would never show.

## Limits

StepShield's trajectories are synthetic code-agent runs with security-flavoured violations, labelled by the paper's authors. Nothing here measures goal drift in customer-service or back-office agents, nothing here tests a commercial drift product (the sales-gated vendors are invited to supply access), and all five judges saw the same prompt, which was tuned on GPT-4.1-mini. Prompt changes are tested on a development split only and never replace the headline rows.

## Reproducing it

`github.com/sod-efi/driftbench`: the harness, the step logs' schema, every `results.json` with the StepShield commit, the intervals, the pre-registration and its addendum, and the scripts that produced each table. Total API spend for everything in this report: US$26.62.

## Right of reply (before publication)

- **Anthropic**: the refusal finding (section 3), with the request IDs available on request. Draft note with the owner.
- **StepShield's authors**: the 200-token cap and parser behaviour (deviation and correction), and the replication. Draft note with the owner.
- **Vendors named in the companion brief** (Lasso, Zenity, Straiker, Noma, Rein and others): invited to supply access for a full run; none is measured here.
