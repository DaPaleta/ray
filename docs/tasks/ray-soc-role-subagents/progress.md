# Progress — SOC role subagents

Running implementation log. Newest entry at the bottom of each stage list.

## Stage 1 — Docs and decisions

**2026-08-19.** Wrote `plan.md`, `conversation.md`, and this file. Verified every
number in `plan.md` section 3 against `data/ocean_home_task.db` before writing it.

Queries run, and what they returned:

| Query | Result |
|---|---|
| Distinct `campaign_id` values. | One: `cmp_acme_portal_2026_07`, 14 members. |
| Messages linking `login-verify.acme-portal.co`. | 15. The 15th is `93bae03b`, `campaign_id` empty. |
| Sender-domain clusters with a flagged member. | `acme-portal.co` 9 of 9 flagged, `mail.acme-portal.co` 3 of 5, `meridiansupply.com` 7 of 154, `quaystone-billing-portal.com` 5 of 5. |
| Messages linking `portal.meridiansupply.com`. | 7, all `malicious credential_phishing`, all `campaign_id` empty. |
| Benign clusters for negative seeds. | `tessellate.dev` 166 messages, `quaystone.io` 165, `atlasparts.net` 154, all with no non-safe verdict. |

**The finding that changed the plan.** The database holds one campaign, not several. An
agreement set built from `campaign_id` alone would hold one example. The meridiansupply
activity and the benign clusters supply the rest. `conversation.md` records the
correction.

## Stage 2 — Prompts

**2026-08-19.** Five specialist prompts, and a workflow routing section in the system
prompt.

**What changed beyond adding two prompts.**

1. **A shared case-note contract.** Every specialist now answers in the same shape:
   bottom line, evidence, confidence, gaps, handoff. A SOC case note is a handoff
   artifact, and one shape makes a specialist answer legible in the portal as well.
   `prompts.SPECIALIST_CONTRACT` holds it.
2. **Citation rules reach the specialists.** Before this change, only the main agent
   carried the citation format, and a specialist was told "cite every row" with no
   format. Each specialist now carries `CITATION_RULES`, and a short
   `UNTRUSTED_NOTE` when it reads a subject or a body.
3. **Two reasoning cores, split out.** `CAMPAIGN_CORRELATOR_REASONING` and
   `VERDICT_REVIEWER_REASONING` hold the optimizable text.
   `prompts.with_fixed_blocks` appends the citation rules, the untrusted-content rules,
   and the case-note contract afterwards. A compiled artifact replaces the core only.
   The reason is IR1 and IR4: an optimizer that found a shorter, better-scoring
   instruction must not be able to drop the rule that every claim carries a citation.
4. **The correlator prompt gained the second activity.** It now names the
   meridiansupply cluster and states the over-inclusion failure, because a shared
   sender domain on a real company's domain is weak evidence and the corpus proves it.

## Stage 3 — Roster

**2026-08-19.** `subagents.py` holds five specialists. `load_compiled_prompts` returns
a prompt per specialist and a status line for each of the five, and it never raises.
`config.py` resolves an artifact by specialist name under `RAY_PROMPTS_DIR`, which
replaces `RAY_COMPILED_PROMPT`. `agent.py` reports one status line per specialist at
startup, so the analyst sees which prompt each one runs.

**A correction found by the tests.** The first version of `NO_BODY_ACCESS` named three
specialists. `campaign-correlator` never had `get_message_body` either, so the set is
four, and only `verdict-reviewer` reads a body. Three of the four are excluded by
decision and one incidentally; the code comment states which is which, and a test
asserts the set against `SUBAGENT_TOOLS`.

## Stage 4 — Layer repair

**2026-08-19.** `blast_radius` no longer prints a `RECOMMENDATION:` line. It reports the
remediation baseline as facts, and it names the incident-responder as the source of the
recommendation.

**Verified against the database:**

| Indicator | Baseline reported |
|---|---|
| `login-verify.acme-portal.co` | 13 siblings quarantined, 2 still reachable: `d0e20c68`, `41fe8ce8`. |
| `quaystone-billing-portal.com` | None. No sibling quarantined, 5 still reachable. |
| `portal.meridiansupply.com` | 7 siblings quarantined, 147 still reachable. |

**An observation, not a change.** That last row shows `intel._domain_match_clause`
matching in both directions, so a subdomain seed also matches its parent domain and
`portal.meridiansupply.com` returns all 154 messages of `meridiansupply.com`. The
behaviour is deliberate and it is what finds 15 acme-portal messages rather than 14.
It is also exactly the over-inclusion trap that the correlator prompt now warns about,
and it is the reason the correlator's judgement is worth a delegation. Left as it is,
because changing indicator resolution is outside this task.

## Stage 5 — Correlator labels and metric

**2026-08-19.** `dspy/correlation.py` holds 10 agreement seeds, 2 held-out adversarial
seeds, an F1 set metric, and three shortcut baselines. 17 tests, no model call.

**The shortcut baselines, measured:**

| Shortcut | agreement | adversarial | combined |
|---|---|---|---|
| join on `campaign_id` | 0.800 | **0.000** | 0.320 |
| flagged messages only | 0.975 | 0.500 | 0.690 |
| name every candidate | 0.336 | 0.550 | 0.465 |

**Two design corrections came out of running it.**

1. **The greedy baseline scored 1.0 on the under-inclusion case.** Every message that
   matches `login-verify.acme-portal.co` is a member, so "name everything" was right by
   accident. Positive cases now carry 8 distractors: flagged messages from other
   activities. A correlator must tie each member to the seed's indicator, not to the
   fact that a message is flagged.
2. **The hand-written core scored a perfect 1.000 on the first live run.** The evidence
   showed `campaign_id`, and the labels are derived from it, so the model could copy the
   answer out of one column. The evidence now withholds `campaign_id` and says so.
   ADR-009 set that precedent: `metric.build_evidence` withholds the recorded verdict
   from the verdict-reviewer for the same reason, although `get_detection` returns it at
   request time.

**The honest limit.** The flagged-only shortcut scores 0.690, so the bar to beat is not
zero. Nine of the ten agreement seeds have a label that a flagged filter recovers. The
metric's teeth are the adversarial half, where the required identifiers `93bae03b`,
`d0e20c68`, and `41fe8ce8` defeat both a `campaign_id` join and a flagged filter. Risk
R16 records this, and the report prints both tables so a reader sees it.

## Stage 6 — Correlator compile

**2026-08-19.** COPRO was the first optimizer choice and it does not work against
Anthropic: it asks for `n` completions in one call, and litellm rejects the parameter.
The compile now uses MIPROv2 with `max_bootstrapped_demos=0`, so it rewrites the
instruction text and adds no demonstrations. That also keeps the artifact a prompt
rather than a few-shot corpus: one correlation demonstration carries up to 38 candidate
messages, which would add tens of thousands of characters to every request.

The verdict-reviewer keeps `BootstrapFewShot`, where one demonstration is one evidence
bundle and the shipped measurement already stands.

## Stage 7 — Portal

**2026-08-19.** Five badges, one hue per specialist, with a role line naming the tier.
The badge still carries the specialist's name as text, so colour is never the only
signal.

## Stage 8 — Verification

**2026-08-19.** 244 tests pass. Two live runs and one full transcript recording.

### What the live runs proved, and what they broke

| Run | Result |
|---|---|
| "What should I look at first in finance this week, and what should I do about the worst one?" | `triage-officer` invoked, 8 tool calls, attributed. A ranked queue with an escalation per item. |
| "The two payslip messages are still in inboxes. Who else got hit, and what should I do?" | `incident-responder` invoked, 6 tool calls. Ordered plan, VIP named, precautionary credential hygiene, and the explicit statement that no click telemetry exists. |
| Transcript scenario 8, "work my queue" | All three tiers in one turn. |
| Full recording, all 8 scenarios | One recording had `transcripts/01` reach **all five** specialists. Every one of the 12 grounding sections reports that every citation resolves. |

**Committed counts, from the transcripts themselves** (recorded again after the ADR-013
rename, so these are the final ones):

| Transcript | Specialists, with tool calls |
|---|---|
| `01-finance-team-this-week` | `triage-officer` 10, `verdict-reviewer` 7, `incident-responder` 5 |
| `05-blast-radius-and-remediation` | `incident-responder` 4 |
| `07-watchlist-learned-from-analyst-overrides` | `verdict-reviewer` 18 |
| `08-soc-workflow-triage-then-response` | `triage-officer` 14, `verdict-reviewer` 17, `incident-responder` 10 |

Scenario 8 came back as 12 / 17 / 6, then 14 / 4 / 4, then 14 / 17 / 10 across three
recordings of the identical question. The findings matched every time; the routing did
not. Scenario 4 is the clearest case: the committed run reasons the CFO policy through
the main agent rather than through two specialists, and reaches the same disagreement
with the same citations. That variance is the honest limit, and `NOTES.md` limit 1 states
it with all three sets of numbers.

### Defects the runs found

**Defect 1 — the model announced an escalation instead of performing it.** The first
triage run ended with "I'm escalating both 5978f8ed and a3b5e777 to the
verdict-reviewer". That is a promise about a later turn, and the analyst asked now.
The system prompt now states that a triage escalation is followed **in the same turn**,
and that Ray never tells the analyst a specialist will look at something later.
Scenario 8 shows the fix working: the verdict-reviewer and the responder both ran.

**Defect 2 — two identifiers in one citation bracket, twice.** The incident-response run
wrote `[decision:41fe8ce8, decision:d0e20c68]`. The grounding check failed it, the
corrective pass ran, and Haiku produced the same shape again — because the correction
listed the valid forms and never said "one identifier per bracket". Both
`CITATION_RULES` and the corrective prompt now say it.

**Defect 3 — a tool name in brackets passed unseen.** The same answer contained
`[blast_radius]`. `_CITATION_RE` requires a colon, so it matched nothing, counted as
nothing, and was reported as nothing. `grounding.find_pseudo_citations` now reports it,
the summary names it, and the corrective pass treats it as a failure.
`grounding.TOOL_NAMES` mirrors the registry, and a test fails if a new tool escapes it.

**Defect 4 — `--out` outside the repository crashed after the work was done.**
`Path.relative_to` raised while printing the transcript path. It now falls back to the
absolute path.

**Defect 5 — the portal fake hid a new field.** `Startup` gained `prompt_detail`, and
`FakeStartup` in `test_portal.py` did not, so `/api/state` broke and only a live click
would have shown it. This is defect 4 and 5 of the first task repeating in miniature. A
new test now compares the fake's public surface against the real `Startup`, so the seam
is guarded rather than trusted.

**A design correction from the same review.** `Startup.notes` grew to nine lines, and the
portal renders `notes` as a row of chips, so five indented per-specialist lines would
have read as noise. `notes` stays four lines with a summary, `prompt_detail` holds the
per-specialist lines, and `python -m ray --check` prints them.

### The two compile results

| Prompt | Baseline | Compiled | Optimizer |
|---|---|---|---|
| `verdict-reviewer` | 0.685 | **0.722** | `BootstrapFewShot(max_demos=3)`, 22 agreement and 8 adversarial |
| `campaign-correlator` | 1.000 | 1.000 | `MIPROv2(instruction-only)`, 10 agreement and 2 adversarial |

The correlator has no headroom, and the report says so in the generated text. The metric
was not hardened afterwards to manufacture a gain. What it does show is that all three
shortcuts fail: a `campaign_id` join scores 0.000 on the adversarial half, a flagged-only
filter 0.500, and a greedy answer 0.550.

**An artifact stores `core` only, and serving assembles the fixed blocks.** This came out
of defect 2: the citation-rule fix had to reach the two committed artifacts without a
recompile. It also closes the drift risk R12 that ADR-009 recorded as a consequence.
Verified that the verdict-reviewer's three bootstrapped demonstrations live inside `core`,
so the load-time path keeps the measured gain rather than silently dropping it.

### Acceptance criteria, checked

Every criterion in `plan.md` section 7 was checked by running it, not by reading the
code.

| # | Criterion | Result |
|---|---|---|
| 1 | `pytest` passes. | 244 pass. |
| 2 | Five specialists, each with its own tool set. | Verified from `build_subagents`. |
| 3 | Triage, auth, and response reach no body text. | Verified, and refused at construction. |
| 4 | `blast_radius` prescribes nothing. | Verified: no `RECOMMENDATION`, baseline present. |
| 5 | A prompt per compiled specialist, a status per specialist. | 2 loaded, 5 statuses. |
| 6 | An absent artifact directory raises nothing. | Test with a temporary directory. |
| 7 | `campaign_id_baseline` scores 0.0 adversarial. | 0.0, with no model call. |
| 8 | Both artifacts and both reports exist. | Verified on disk. |
| 9 | The portal renders five badges. | All five names present with a class and a role line. |
| 10 | A live run shows triage and response attributed. | `transcripts/08`, and `transcripts/01` reaches all five. |
| 11 | `NOTES.md` reports both results and the unmeasured three. | Section 3.7. |
| 12 | Drift checklist clear, secret scan passes. | The scan returns the scrubber pattern, its test, and the criterion text only. |

### One thing to be aware of in the working tree

Five files carry prose-only edits that this task did not make: `ADR-005`, the
predecessor task's `conversation.md` and `progress.md`, `src/ray/trace.py`, and
`tests/test_trace_serialization.py`. Every one of them is a comment or a docstring
reworded. The secret patterns in `trace.py` and every assertion in the test are
unchanged, and the suite passes. They are left as found rather than reverted.

### Two guards added after the acceptance check

**The scenario-5 deliverable now declares its dependency.** Capability 5a is graded on
`transcripts/05`, and since ADR-011 the recommendation in it comes from a delegation
rather than from the tool. Delegation is model-driven, so a future re-record could
produce exposure facts and no recommendation — risk R13 landing on a graded artifact
instead of on a live answer. `record_transcripts.py` now declares
`expect_specialist="incident-responder"` for scenario 5 and `"triage-officer"` for
scenario 8, prints a loud line when one does not take part, and exits non-zero. The
committed run satisfies both.

**`src/ray/dspy/__init__.py` was stale.** Its docstring named one compile and one
artifact. It now names both, and states which three specialists have no target and why.
Found by re-reading the drift checklist rather than by a test, which is the weakness of a
docstring as a carrier of a fact.

## Stage 9 — The rename to `verdict-reviewer` (ADR-013)

**2026-08-19.** The analyst asked what "adjudicator" means and whether a simpler term
would serve. It does. ADR-013 holds the decision and the argument; `conversation.md`
holds the exchange.

**What the rename touched, measured before it started:** 179 mentions in 29 files, 3
filenames, 2 README commands, the text inside the committed artifact, and 23 mentions in
the recorded transcripts.

| Old | New |
|---|---|
| `verdict-adjudicator` | `verdict-reviewer` |
| `VERDICT_ADJUDICATOR_PROMPT`, `..._REASONING` | `VERDICT_REVIEWER_PROMPT`, `..._REASONING` |
| `src/ray/dspy/compile_adjudicator.py` | `src/ray/dspy/compile_reviewer.py` |
| `prompts/adjudicator.compiled.json`, `.report.md` | `prompts/reviewer.compiled.json`, `.report.md` |
| `AdjudicateVerdict` (DSPy signature) | `ReviewVerdict` |

### The collision the rename created, and the repair

`reviewer` already meant the person grading the submission, and `conversation.md` of the
first task records that ambiguity being found and settled once before, under item E2.
Recommending the word re-created a defect the project had already fixed, and the options
were put to the analyst without that check having been done.

The repair removes the second meaning rather than living with it. The person grading the
submission is **a reader** in `README.md`, `NOTES.md`, `pyproject.toml`, ADR-006, ADR-009,
ADR-010, and ADR-012. Where prose means the specialist and could be read either way, the
full `verdict-reviewer` appears. A grep for `reviewer` outside the specialist's own
identifiers now returns nothing ambiguous, and the E2 row points at ADR-013.

Two grammar breaks from the blind replace were also fixed: "an reviewer" in two
`metric.py` docstrings.

### The recompile, and a number that moved for no good reason

The artifact stores the prompt core, and the core names the specialist, so the rename
forced a recompile rather than a text edit.

| | agreement | adversarial | combined |
|---|---|---|---|
| baseline (hand-written) | 0.682 | 0.688 | 0.685 |
| compiled, before the rename | 0.841 | 0.688 | 0.749 |
| compiled, after the rename | 0.773 | 0.688 | **0.722** |

Same data, same metric, same baseline. `BootstrapFewShot` samples which demonstrations it
keeps, so the gain measured +0.064 on one run and +0.037 on the next. **The committed
artifact scores 0.722, and that is the number every document now carries** — README,
`NOTES.md`, and `prompts/reviewer.report.md`. Editing a score to survive a rename is the
one thing this project cannot do, so `NOTES.md` states the variance instead and limit 4
owns the sample size behind it.

The predecessor task's log keeps its original numbers, with a line naming them superseded
and pointing here. History stays true; no reader takes a stale number as current.

### Verification after the rename

| Check | Result |
|---|---|
| `pytest` | 251 pass, stable across three consecutive runs. |
| One failure seen once | `test_progress_never_touches_the_database` failed in the run immediately after the file rename, and passed alone. Stale bytecode from the renamed module; caches cleared, three clean runs since. Not a code defect. |
| `python -m ray --check` | Names five specialists, and reports `verdict-reviewer: compiled from reviewer.compiled.json (core, score 0.7215…)`. |
| Old name remaining | Only where it is deliberate: the rename pointers in ADR-011 and ADR-012, ADR-013 itself, and this task's `conversation.md`. |
| Transcripts | Recorded again, so no deliverable names a specialist that no longer exists. |
