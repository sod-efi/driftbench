# 2026-10-26-holdout-free

Split: holdout; StepShield 031aa88219f7; prompt v1.

| Detector | FPR on clean | Recall on rogue | EIR (k=3) | Premature alerts | Mean gap (steps) | Cost USD |
|---|---|---|---|---|---|---|
| StaticGuard | 77.8% [69.1, 84.6] | 86.1% [78.3, 91.4] | 22.6% [15.3, 32.1] | 76.3% [66.8, 83.8] | -5.04 [-5.97, -4.13] | 0.00 |
| ConstraintGuard | 25.0% [17.8, 33.9] | 24.1% [17.0, 32.9] | 7.7% [2.1, 24.1] | 88.5% [71.0, 96.0] | -5.35 [-6.92, -3.62] | 0.00 |

| Pair | Agree on detected | Kappa | Rogue both caught | Same step | Mean step diff |
|---|---|---|---|---|---|
| StaticGuard vs ConstraintGuard | 30.6% | -0.05 | 20 | 2 | 3.95 |
