# Adjudicator compile report

Model: `claude-haiku-4-5-20251001`

Metric: Two-sided (ADR-009): score_verdict grades a predicted verdict against an expected one on a 3-point scale (exact match 1.0, suspicious-vs-malicious 0.5, crossing the safe/not-safe boundary 0.0). The combined score weights the 8 held-out adversarial rows (recorded verdict is wrong) at 60% and a balanced sample of the recorded decisions (agreement set) at 40%, so a constant 'safe' answer — which would score over 98% on agreement alone — scores 0.0 on the adversarial half.

| | agreement | adversarial | combined |
|---|---|---|---|
| baseline (hand-written) | 0.625 | 0.688 | 0.662 |
| compiled (DSPy) | 0.833 | 0.688 | 0.746 |

n_agreement = 12, n_adversarial = 8
