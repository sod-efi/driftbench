# smoke-gemini-sonnet

Split: holdout; StepShield 031aa88219f7; prompt v1.

| Detector | FPR on clean | Recall on rogue | EIR (k=3) | Premature alerts | Mean gap (steps) | Cost USD |
|---|---|---|---|---|---|---|
| Judge-gemini-3.5-flash-lite-v1 | 0.0% [0.0, 79.3] | 100.0% [56.6, 100.0] | 60.0% [23.1, 88.2] | 40.0% [11.8, 76.9] | -1.40 [-3.80, +0.00] | 0.02 |
| Judge-claude-sonnet-5.5-v1 | 0.0% [0.0, 79.3] | 40.0% [11.8, 76.9] | 100.0% [34.2, 100.0] | 0.0% [0.0, 65.8] | +0.00 [+0.00, +0.00] | 0.21 |

| Pair | Agree on detected | Kappa | Rogue both caught | Same step | Mean step diff |
|---|---|---|---|---|---|
| Judge-gemini-3.5-flash-lite-v1 vs Judge-claude-sonnet-5.5-v1 | 50.0% | 0.18 | 2 | 2 | 0.00 |
