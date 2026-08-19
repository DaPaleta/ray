# Conversation — SOC role subagents

Decisions, questions, and analyst guidance for this task. `plan.md` owns the design.

## 2026-08-19 — The request, and the scope check

The analyst asked for two improvements, and asked whether each one fits the vision.

1. Make the specialists work the way a real SOC works: an incident-response role that
   suggests recommendations, a triage role that analyzes the data and acts on alerts.
2. Write the specialist prompts with DSPy.

### What the scope check found

**In scope already.** A remediation recommendation is capability 5a. "What to do next"
is one of the three things `docs/vision.md` section 1 says Ray exists for. A build-time
compile of another prompt is untouched by section 4.2 item 8, which excludes prompt
optimization at request time only.

**Not in scope as written, and the exact blocking lines.**

- ADR-008: "Three, and no more. A fourth subagent would need a fourth such task."
- `docs/vision.md` section 3: "**subagent** — One of the three specialists in ADR-008."
- `docs/structure.md` section 3a enumerates the three.
- IR9 and `docs/vision.md` section 4.2 item 7 forbid an alert feed or a poller. So
  "acting on alerts" can only mean working a queue of recorded rows and
  `watchlist_sweep` matches, and acting can only mean prioritize, escalate, and
  recommend.
- ADR-009 rejected a second compile target because it had no ground-truth labels. That
  test now applies per prompt, and it rules out a compiled triage prompt and a
  compiled response prompt.

### The finding that strengthened the request

`src/ray/tools/exposure.py` computes a remediation recommendation inside the tool, from
one rule. IR7 forbids a tool that returns a judgement. So `incident-responder` is not
an addition on top of a clean design. It moves an existing violation to the correct
layer.

### The analyst's decisions

| Question | Decision |
|---|---|
| How to record the work. | A new task folder, plus ADR-011 and ADR-012. The predecessor task is shipped, and its record stays intact. |
| Roster and DSPy scope. | Add `triage-officer` and `incident-responder`. Compile `campaign-correlator` against real labels. Leave triage and response hand-written. |

Two options were declined: a reframe of the three prompts with no new roles, and a
compile of `auth-forensics` against a rule-derived label. The second was declined
because the label would be computed by the same rule the prompt states, so the metric
would be partly circular.

## 2026-08-19 — What the data changed about the plan

The first sketch of the correlator labels said "recorded `campaign_id` as the agreement
set". A query then showed that the database holds exactly **one** campaign, with 14
members. An agreement set of one example is not a training set.

Two queries fixed the design.

1. A second attacker activity exists and carries **no** `campaign_id` at all: 7
   messages from `statements@meridiansupply.com`, all `malicious credential_phishing`,
   all linking `portal.meridiansupply.com`, inside a sender domain that sends 154
   messages of which 147 are legitimate.
2. The benign sender clusters supply negative seeds. `tessellate.dev` sends 166
   messages and holds no non-safe verdict, so a shared sender domain alone is not an
   attacker activity.

`plan.md` section 4.3 holds the metric that came out of this. The adversarial half now
covers both failure directions: under-inclusion, which a `campaign_id` join commits,
and over-inclusion, which a whole-domain join commits.

## Deferred

1. **A compiled routing prompt.** The main agent decides which specialist to call, and
   no recorded label says which call is correct. ADR-009 already rejected this shape.
2. **A compiled `auth-forensics` prompt.** Declined above. Revisit only with a label
   that does not restate the prompt's own rule.
3. **A sixth specialist for user-report intake.** A real SOC triages user-reported
   phishing. This database holds no report table, so the role would have no input.

## 2026-08-19 — The specialist is renamed to `verdict-reviewer`

The analyst asked what "adjudicator" means, and whether a simpler English term would do.

**The answer given.** An adjudicator, from Latin *adjudicare*, is the party that formally
settles a dispute: a judge or a referee. It is precise for what the specialist does. Two
facts in this repository argued against it anyway. `AGENTS.md` section 5 requires
Simplified Technical English, whose controlled vocabulary holds `review` and not
`adjudicate`; and the question itself is the evidence that the term cost a reader a
lookup, which is what a terminology table exists to prevent.

**The cost, measured before the decision.** 179 mentions in 29 files, 3 filenames, 2
README commands, the text inside the committed compiled artifact, and 23 mentions in the
recorded transcripts. So the rename meant a recompile and a re-record, not a search and
replace.

**The analyst chose** `verdict-reviewer`, and chose to carry it everywhere, including the
recompile and the re-record. `verdict-checker` and `second-opinion` were declined;
ADR-013 records why each one lost.

### The collision I should have raised before the choice

I offered `verdict-reviewer` without checking what "reviewer" already meant in this
repository. It meant the person grading the submission — and `conversation.md` of the
first task records that exact ambiguity being found and settled once already, under item
E2. Recommending the word re-created a defect the project had already fixed.

It is repaired rather than tolerated: the person grading the submission is now **a
reader**, in `README.md`, `NOTES.md`, `pyproject.toml`, ADR-006, ADR-009, ADR-010, and
ADR-012. "Reviewer" now names one thing. Where a sentence means the specialist and could
be read either way, the full `verdict-reviewer` appears. ADR-013 decision item 2 owns
this, and the E2 row now points at it.

**What I would do differently.** Check what a proposed name already means in the
repository before offering it, not after. A rename that introduces an ambiguity is worse
than the Latinate word it replaced.
