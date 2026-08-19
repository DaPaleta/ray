# ADR-012: Compile every prompt that the database labels, and no other

**Date:** 2026-08-19
**Status:** accepted
**Renamed by:** ADR-013, which changed `verdict-adjudicator` to `verdict-reviewer`
and `adjudicator.compiled.json` to `reviewer.compiled.json`.
**Extends:** ADR-009, which compiles one prompt offline into a static artifact. The
mechanism is unchanged. This record generalizes it to more than one prompt, and it
states the test that decides which prompts qualify.

## Context

The analyst asked for the specialist prompts to be written with DSPy. ADR-009 compiles
one of them. It also refused a second target, and the reason it gave is the reason that
governs this record: "The router has no ground-truth labels, so its metric would rest on
an opinion."

ADR-011 raises the roster to five prompts. So the question is per prompt, and the test is
the one ADR-009 already applied: does the database hold a label for what this specialist
outputs?

| Specialist | Output | Recorded label? |
|---|---|---|
| `verdict-reviewer` | A verdict for one message. | **Yes.** 2288 rows in `decisions`, and the 8 rows whose recorded verdict is wrong. ADR-009 built both sets. |
| `campaign-correlator` | The set of messages in one activity. | **Yes.** `campaign_id`, `verdict`, and `attack_type` support a set label for every seed. Section "The correlator labels" holds the construction. |
| `auth-forensics` | Whether authentication supports the claimed sender. | **No usable label.** A label is derivable from the sender domain, the three authentication fields, and a display-name lookup. That is the same rule the prompt states, so the metric would score the rule against itself. |
| `triage-officer` | A priority order over a queue. | **No.** No table records which item an analyst worked first. |
| `incident-responder` | A response plan. | **No.** `remediations` holds 38 rows of action taken, and no row holds a sequence, a notification scope, or a rationale. |

## Decision

**Compile two prompts. Hand-write three. State the boundary in `NOTES.md`.**

1. **The rule.** A prompt is compiled only against a label that a recorded row supplies.
   `plan.md` of this task records the rule as IR11. A metric that scores a prompt against
   an opinion this repository wrote is not a measurement, and shipping one would weaken
   the measured claim that ADR-009 exists to make.

2. **One artifact per specialist.** `prompts/reviewer.compiled.json` keeps its name and
   its meaning. `prompts/correlator.compiled.json` joins it. `config.py` resolves an
   artifact by specialist name under a prompts directory, which `RAY_PROMPTS_DIR` sets.
   `subagents.py` loads and falls back **per specialist**, and it reports a status line
   for each of the five. An absent artifact stays a supported state. IR8 holds.

3. **An artifact stores the reasoning core, and serving assembles the rest.** An
   optimizer rewrites the core only. The citation rules, the untrusted-content rules,
   and the case-note contract are appended by `prompts.with_fixed_blocks` at load time,
   so an edit to a safety block reaches a compiled prompt without a recompile. IR1 and
   IR4 do not bend to a metric, and they must not go stale inside a committed artifact
   either. The artifact also stores the fully assembled `prompt` for human review, and
   an older artifact that holds only `prompt` still loads.

4. **The correlator metric is two-sided, and its adversarial half covers both failure
   directions.** The unit is a set of message identifiers, and the score is the F1 of the
   predicted set against the expected set. F1 punishes both failures: recall punishes the
   member a correlator misses, and precision punishes the message it wrongly includes.

   - **Under-inclusion.** Seed the link domain `login-verify.acme-portal.co`. The expected
     set holds 15 members, and the 15th is `93bae03b`, whose `campaign_id` is empty. The
     score is multiplied by zero unless `93bae03b` appears, so a `campaign_id` join scores
     **0.0**. This is the analogue of ADR-009's constant `safe` answer.
   - **Over-inclusion.** Seed the sender domain `meridiansupply.com`. The domain sends 154
     messages, and 7 are `malicious credential_phishing` with an empty `campaign_id`. The
     expected set holds those 7. An answer of "every message from this domain" scores an
     F1 of about 0.09.

   Both adversarial seeds are held out of few-shot bootstrapping, exactly as ADR-009 holds
   out its 8 rows.

5. **The agreement half holds positive seeds and negative seeds.** A positive seed expects
   the members that recorded rows support: a sender domain, or one subject pretext. A
   negative seed expects the **empty set**: `tessellate.dev` sends 166 messages and holds
   no non-safe verdict, so a shared sender domain alone is not an attacker activity. The
   negative seeds are what stop a correlator from scoring well by returning every message
   that shares any indicator.

6. **`correlation.py` ships the baseline function.** `campaign_id_baseline` is the analogue
   of ADR-009's `constant_safe_baseline`. It scores 0.0 on the adversarial half, and a test
   asserts that with no model call and no DSPy import.

7. **Both reports ship.** `prompts/reviewer.report.md` and `prompts/correlator.report.md`
   each hold a before-and-after table with `n_agreement` and `n_adversarial`. `NOTES.md`
   carries both, and it states that three prompts stay hand-written because no recorded
   label exists for them.

## Alternatives Considered

**Compile all five prompts.** Rejected. Three of the five would be scored against a rubric
written by this repository. That produces a number with no evidence behind it, and a reader
who checks the metric finds an opinion. ADR-009 refused this shape once already.

**Compile `auth-forensics` against a rule-derived label.** Rejected, and the analyst
declined it when it was offered. The label would come from the sender domain, the three
authentication fields, and a display-name lookup, which is the rule the prompt states. A
metric built that way measures the label generator.

**One artifact holding a map of specialist name to prompt.** Rejected. ADR-009's follow-up
requires each artifact to ship with the score that produced it. One file for two compiles
means one file changes whenever either compile runs, and a reader then cannot tell which
score belongs to which prompt without a diff.

**Optimize the correlator with the same optimizer call as the verdict-reviewer.** Rejected. The
two have different signatures, different label sets, and different metrics, so one script
would carry two unrelated paths. Two scripts of about 200 lines each stay readable, and
each one writes its own artifact and its own report.

## Consequences

**Positive.** The project now reports a measured number for two of the five prompts, and it
states plainly why the other three carry none. The correlator metric is sharper than the
verdict-reviewer's in one respect: its adversarial half fails both a lazy join on `campaign_id`
and a greedy join on a whole domain, so neither shortcut can pass. The per-specialist
artifact keeps ADR-009's follow-up rule intact.

**Negative.** The correlator adversarial half rests on 2 examples against the verdict-reviewer's
8, so its number carries less weight; risk R15 records this and every report prints
`n_adversarial` beside the score. The compile now costs two model-call budgets instead of
one. The labels come from a shared-indicator reading of recorded rows, so the metric
measures agreement with that reading rather than with an external ground truth; risk R16
records the limit and `NOTES.md` states it.

**Follow-up.** Commit each artifact together with the score that produced it, and print
`n_agreement` and `n_adversarial` in both reports. When a specialist gains a recorded label
later, IR11 admits it to the compile; until then it stays hand-written.
