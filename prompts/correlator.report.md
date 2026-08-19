# Correlator compile report

Model: `claude-haiku-4-5-20251001`

Optimizer: MIPROv2(instruction-only, num_candidates=6, num_trials=8)

Metric: Two-sided over message-identifier sets (ADR-012): score_membership grades a predicted member set against the expected set by F1, so recall punishes a member missed and precision punishes a message wrongly included. A missing required identifier sets the score to 0.0. The combined score weights the 2 held-out adversarial seeds at 60% and the 10 agreement seeds at 40%. The adversarial half refuses every single-field shortcut: a campaign_id join misses 93bae03b, a flagged-only filter misses the recorded-safe members d0e20c68 and 41fe8ce8, and a greedy answer loses precision on a sender domain that sends 154 messages of which 7 are the activity.

## Shortcut baselines — no model call

Each row is a correlator that needs no model. The metric exists to refuse them.

| shortcut | agreement | adversarial | combined |
|---|---|---|---|
| campaign_id join | 0.800 | 0.000 | 0.320 |
| flagged messages only | 0.975 | 0.500 | 0.690 |
| name every candidate | 0.336 | 0.550 | 0.465 |

## Prompt

| | agreement | adversarial | combined |
|---|---|---|---|
| baseline (hand-written core) | 1.000 | 1.000 | 1.000 |
| compiled (DSPy) | 1.000 | 1.000 | 1.000 |

n_agreement = 10, n_adversarial = 2

The bar to beat is the strongest shortcut, not zero. Read the two tables together.

**No headroom.** The hand-written core already scores 1.000 on both halves, so no instruction can beat it on this metric. The optimizer ran and kept the incumbent. What the measurement shows is that the three shortcuts fail and the hand-written prompt does not. The metric was not hardened afterwards to manufacture a gain, because tuning a metric towards a wanted result is the failure ADR-012 exists to prevent.
