# 2026-10-27-holdout-judges-2

Split: holdout; StepShield 031aa88219f7; prompt v1; failed steps re-judged 2026-10-27 (max_tokens 600).

| Detector | FPR on clean | Recall on rogue | EIR (k=3) | Premature alerts | Mean gap (steps) | Cost USD |
|---|---|---|---|---|---|---|
| Judge-gemini-3.5-flash-lite-v1 | 15.7% [10.1, 23.8] | 98.1% [93.5, 99.5] | 91.5% [84.6, 95.5] | 8.5% [4.5, 15.4] | -0.52 [-0.92, -0.19] | 0.88 |
| Judge-claude-sonnet-5.5-v1 | 14.8% [9.3, 22.7] | 68.5% [59.3, 76.5] | 86.5% [76.9, 92.5] | 10.8% [5.6, 19.9] | -0.20 [-0.86, +0.38] | 8.73 |

| Pair | Agree on detected | Kappa | Rogue both caught | Same step | Mean step diff |
|---|---|---|---|---|---|
| Judge-gemini-3.5-flash-lite-v1 vs Judge-claude-sonnet-5.5-v1 | 76.4% | 0.54 | 73 | 50 | 0.99 |
