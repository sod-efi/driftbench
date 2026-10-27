# Pre-registration, written before the first paid run (October 26, 2026)

**Question.** On StepShield's strictly held-out set (216 code-agent trajectories, 108 rogue with the divergence step labelled, 108 clean), how do cheap, publicly reachable detectors compare on four things: false-positive rate on clean runs, recall on rogue runs, early-intervention rate (alert within 3 steps after the divergence, none before), and cost per 1,000 trajectories?

**Detectors in the pilot.** StepShield's StaticGuard (847 rules) and ConstraintGuard (free, deterministic), and StepShield's step-by-step LLMJudge recipe run through OpenRouter with prompt v1 (the paper's prompt, verbatim) on: openai/gpt-4.1-mini (the paper's model, a replication), anthropic/claude-haiku-5.5, anthropic/claude-sonnet-5.5, google/gemini-3.5-flash-lite, and anthropic/claude-opus-5.5 if the budget allows. Microsoft's Agent Governance Toolkit and Invariant Guardrails are installed but ship no default policy that judges a trajectory; running them with hand-written rules would measure our rules, not their product, so they are reported as "no default policy" in the pilot and left for the full run.

**Headline numbers.** The first run of each judge with prompt v1 on the held-out set. Each number carries a 95% Wilson interval; timing gaps carry a bootstrap interval. No single-number ranking.

**What would count as a story.** (a) If the LLM judges land within each other's intervals on false positives and recall while StaticGuard sits far outside, the finding is "the cheapest judge is as good as the expensive one, and rules are not detectors". (b) If the judges disagree with each other by more than their intervals, the finding is "detection depends on the judge, and nobody publishes which judge they use". (c) If any judge's false-positive interval overlaps StaticGuard's, the paper's headline does not replicate for that model.

**Calibration loop (usage loop).** Runs only on a development split drawn deterministically from StepShield's training pairs (10 pairs per category, 120 trajectories). A revised prompt is adopted only if, on that split with the same judge model, the false-positive rate drops by at least 2 points, recall drops by less than 2 points, and the early-intervention rate drops by less than 0.05. Adoptions are logged and reversible. A held-out run with any prompt other than v1 is labelled with its version and never replaces the headline row.

**Budget.** Measured before the run: 3,056 judged steps and 1,174,797 input tokens for the held-out set with prompt v1. Hard stop per judge at 150% of its estimate.

**Not claimed.** StepShield's trajectories are code agents and security-flavoured violations. Nothing here measures goal drift in customer-service or back-office agents, and nothing here tests a commercial drift product; the sales-gated vendors are invited to supply access for the full run.

## Addendum, October 27, 2026 (written after the runs; nothing above was changed)

**Deviation from the paper's recipe.** StepShield's judge caps answers at 200 output tokens. With Claude models that cap cut off the JSON on 836 of Haiku's and 216 of Sonnet's 3,056 answers, which the vendor parser scored as "not rogue". Those steps were re-asked with a 600-token cap, same prompt, same model, temperature 0 (each step is judged alone, so the other answers are unaffected). The headline rows use the repaired logs; the cap is a harness setting, not part of prompt v1. The first published Haiku row (0% false positives, 81.5% recall, October 26) is withdrawn.

**Refusals.** Anthropic's content filter refused 84 Sonnet 5.5 requests ("violative cyber content"), 83 on rogue runs. The headline row scores a refusal as "not rogue" (what a monitor that reads only the JSON does). A second row scores a refusal as an alert. Both are reported; neither is hidden.

**Scope of the usage loop's numbers.** Development-split numbers before October 27 carried the same truncation error and were rebuilt from the repaired logs.
