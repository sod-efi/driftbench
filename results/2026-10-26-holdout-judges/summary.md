# 2026-10-26-holdout-judges

Split: holdout; StepShield 031aa88219f7; prompt v1; failed steps re-judged 2026-10-27 (max_tokens 600).

| Detector | FPR on clean | Recall on rogue | EIR (k=3) | Premature alerts | Mean gap (steps) | Cost USD |
|---|---|---|---|---|---|---|
| Judge-claude-haiku-5.5-v1 | 24.1% [17.0, 32.9] | 99.1% [94.9, 99.8] | 91.6% [84.8, 95.5] | 8.4% [4.5, 15.2] | -0.41 [-0.77, -0.13] | 0.62 |
| Judge-gpt-4.1-mini-v1 | 5.6% [2.6, 11.6] | 96.3% [90.9, 98.6] | 91.3% [84.4, 95.4] | 8.7% [4.6, 15.6] | -0.42 [-0.78, -0.12] | 0.75 |

| Pair | Agree on detected | Kappa | Rogue both caught | Same step | Mean step diff |
|---|---|---|---|---|---|
| Judge-claude-haiku-5.5-v1 vs Judge-gpt-4.1-mini-v1 | 86.6% | 0.73 | 104 | 89 | 0.62 |
