# Progress — Ray, the email-threat investigator agent

**Task:** `docs/tasks/ray-email-threat-investigator/`
**Plan:** `plan.md` section 5 owns the stage list.

---

## Current state — read this first

*This section is the answer to "what is done, how do I run it, and how do I request a
change". It is updated at the end of every stage.*

**Last updated:** session end. **All three tiers complete. 206 tests pass with no API
key.** `NOTES.md` is the submission write-up and the best place to start.

### What works right now

| Capability | State | How it is proven |
|---|---|---|
| Configuration, read-only access, time resolution | working | 30 tests; both time traps closed |
| Prompt-injection detection | working | All 6 planted messages, **0 false positives across 2288** |
| Grounding verification | working | 23 tests, including citation forgery by SQL wildcard |
| The 11 tools | working | `test_core_tools`, `test_intel_tools`, `test_exposure`, `test_watchlist` |
| Memory: provenance and confirm gate | working | 19 tests; the poison payload is refused and traced to its message |
| Agent, 3 subagents, delegation, attribution | working | Live runs; both specialists fire on scenario 4 |
| Capability 5a blast radius | working | 15 recipients, 7 departments, 1 VIP, the 2 live messages named |
| Capability 5b watchlist loop | working | `transcripts/07`: audit, propose, confirm, sweep |
| Compiled adjudicator prompt | working | Loads with score 0.7458; baseline 0.6625 |
| Portal, graph, trace, specialist badge | working | 11 tests; self-contained page verified |
| Secret hygiene | working | 3 layers, 4 guards; see defect 6 |
| Transcripts | 7 recorded | `transcripts/`, reproducible from `scripts/` |

### How to run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q                    # 206 tests, no key needed
python -m ray --check        # readiness, calls no model

export OCEAN_ANTHROPIC_KEY=...
python -m ray                                  # the portal, http://127.0.0.1:8765
python -m ray --ask "Anything targeting finance this week?"
python scripts/record_transcripts.py --list    # the 7 recorded scenarios
```

The committed database is untouched: `agent_memory` is still empty, because the
recorder works on a scratch copy.

### Known limits

`NOTES.md` section 7 owns this list. In short: the model is Haiku and not the
`gpt-5.6-luna` the brief names (ADR-005); delegation is model-driven and Haiku does not
delegate on every trigger; a corrective re-cite pass compensates for weak citation
discipline; nothing verifies that *every* claim is cited, only that every citation
resolves; the DSPy label sets are small; and the work exceeded the brief's 3 hours.

### How to request a change

Name the stage or the file. A change to a decision goes to the ADR that owns it, and
a change to scope goes to `plan.md`. `AGENTS.md` section 4 holds the drift checklist
that keeps each fact in one place.

---

## Stage status

`plan.md` section 5 owns the tiers and the minute estimates.

| Tier | # | Stage | Status |
|---|---|---|---|
| — | 0 | Exploration and planning | **done** |
| 1 | 1 | Bootstrap | **done** |
| 1 | 2 | Data layer | **done** |
| 1 | 3 | Core tools | **done** |
| 1 | 4 | Intel tools | **done** |
| 1 | 5 | Injection and grounding | **done** |
| 1 | 6 | Agent, subagents, and memory | **done** — live run verified |
| 1 | 7 | One-shot runner and transcripts | **done** — 7 transcripts recorded |
| 1 | 8 | Write-up | **done** — `NOTES.md` |
| 2 | 9 | Capability 5a and 5b | **done** |
| 2 | 10 | DSPy compile | **done** — 0.6625 to 0.7458 |
| 3 | 11 | Portal, graph, and trace | **done** |

Stages 2 to 5 need no key. Stage 6 onward needs `OCEAN_ANTHROPIC_KEY`, which the
analyst supplied, so no stage is blocked.

## Log

### 2026-08-19 — Exploration

Read the brief at `docs/home-task-brief.pdf`. Explored every table in
`data/ocean_home_task.db`. `plan.md` section 2 records the full result. The
findings that changed the design:

1. `agent_memory` is empty and holds a `source` column. The schema expects Ray to
   write there with provenance. This drove ADR-003.
2. `sender-reputation` ran on 2 messages only, and `stage2` ran on 38. An absent
   analyzer result is not a benign analyzer result. Tool 4 reports the analyzers
   that did not run.
3. Message `93bae03b` carries no `campaign_id`, although its `stage2` reasoning
   names the acme-portal campaign in prose. A campaign join on `campaign_id` alone
   loses this message. `domain_intel` and `entity_graph` join on the shared
   indicator instead. (An entry later in this log corrects how absence is stored:
   the column is `NULL`, not an empty string.)
4. Two campaign members, `d0e20c68` and `41fe8ce8`, are recorded `safe` on an
   unscanned link whose URL is byte-identical to a URL that 13 other messages
   carry with a malicious verdict. These are false negatives that Ray can find.
5. `db_meta.data_as_of` is `2026-08-16T09:00:00Z`, but the newest message arrives
   at `2026-08-16T17:10:57Z`. A window that ends at `data_as_of` drops rows. The
   resolver therefore applies no upper bound.
6. Six messages carry a prompt injection, across five distinct patterns. They are
   a test corpus for requirement 3.
7. No table holds click data or EDR data. Scenario 3 asks about a click, so it is
   the natural "does not know" transcript.

### 2026-08-19 — Stack verification

Verified the load-bearing assumption before writing the plan, because a failure
here would change the architecture rather than a detail.

- `deepagents` 0.7.7 requires Python `>=3.11`. The local interpreter is 3.12.12.
- `create_deep_agent` accepts `model: str | BaseChatModel`. A custom
  `ChatOpenAI` instance therefore wires in cleanly, and the Anthropic default
  does not block `gpt-5.6-luna`.
- `deepagents` does not depend on `langchain-openai`. This project adds the
  dependency itself.

### 2026-08-19 — Planning

Presented three approaches. Chose approach B, the typed parameterized tool set.
ADR-001 records the reason. Wrote five ADRs and the docs structure.

Corrected three claims in the first draft of `plan.md` against the database:

1. The finance window holds 7 flagged messages, not 4. The first draft omitted
   `7562b53c` and both released quaystone messages.
2. Two released quaystone messages reached `finance`, not 3. The other 3 reached
   `operations` and `sales`.
3. Identified the sixth injected message as `38816400`.

While correcting item 1, found a stronger fact: message `276266c0`, the CFO
impersonation, carries verdict `safe` and an empty attack type. No verdict filter
and no attack-type filter returns it. Only the stored CFO policy surfaces it.
`plan.md` section 2.4 now records this as the argument for capability 4.

Verified the acceptance criteria against the database and corrected three more
claims:

4. Every one of the 15 acme-portal messages holds a remediation row. The first
   draft claimed that the 2 false negatives hold none. They hold
   `action = 'none'`, while the other 13 hold `action = 'quarantined'`. An
   explicit `none` is stronger evidence than an absent row, so criterion 16 now
   asserts the recorded value.
5. Assumption A3 now lists three inbox states, not one: `none`, `released`, and
   absent. Only `quarantined` removes a message.
6. The 15 acme-portal recipients span 7 departments, not 6. Exactly one is a VIP:
   Talia Moreau in `exec`.

This is the reason for rule 5 in `AGENTS.md` section 7: run the query, and do not
restate a number from memory.

### 2026-08-19 — Bootstrap

Created the repository skeleton, `AGENTS.md`, `README.md`, `requirements.txt`,
`.gitignore`, and `.env.example`. Copied the supplied database to
`data/ocean_home_task.db` per ADR-006. Ran `git init`. Made no commit.

### 2026-08-19 — Session 2: scope revision

The analyst described the project as they had imagined it, and the comparison
changed the architecture in four ways. `conversation.md` records the question round.

**What the analyst got right, and the first design got wrong.**

1. **`deepagents` takes `subagents` natively.** The first design used one agent
   with 14 flat tools, which under-used the required harness and put reasoning
   inside tools where no prompt can reach it. ADR-008 now defines three
   specialists. Three tools became subagents: `sender_intel`, `campaign_intel`, and
   `review_analyst_overrides`.
2. **Explainability deserves an artifact, not a property.** The grounding check was
   a silent post-check that emitted a warning. It now renders. `trace.py` records
   the tool-call log, and the portal shows it.
3. **Graph traversal was already in the design, in table form.** `campaign_intel`
   and `domain_intel` were traversing a graph and returning rows. `entity_graph`
   replaces `campaign_intel` and earns its place three times: it is the graph
   resource, it renders as the portal visualization, and it is how the
   campaign-correlator finds `93bae03b`.
4. **Three tools collapsed into one.** `get_detection` returns the analyzer
   results, the decision, and the remediation together, because they are always
   needed together and because that is exactly the adjudicator's input.

Tool count fell from 14 to 9.

**Where the first design pushed back, and the push held.** The analyst proposed
real-time event reports. Nothing appends to the database, so a live feed would
replay `received_at` as if it were arriving now, and Ray would state a fact that no
row supports. Cut, and replaced with the watchlist sweep in ADR-010. The analyst
agreed.

**DSPy.** Accepted in one narrow form. The insight that made it affordable: compile
offline and serve a static artifact, so DSPy never enters the request path. The
database supplies real labels on both sides, which is what makes the metric
defensible. See ADR-009. Timeboxed to 35 minutes, with the evaluation harness as
the fallback.

**Model.** Switched to Claude Haiku 4.5 through `OCEAN_ANTHROPIC_KEY`. The OpenAI
key never received credit. This deviates from the brief, which names
`gpt-5.6-luna`, so criterion 31 makes the disclosure in `NOTES.md` mandatory. The
substitution removes a dependency, because `deepagents` already ships
`langchain-anthropic`. ADR-005 was rewritten and now supersedes its own earlier
OpenAI form.

**Budget.** The three tiers total about 195 minutes of implementation against a
3-hour brief. `plan.md` section 5 states the overrun openly rather than implying
that all of it fits, and it orders the work into three cut lines. Stage 7 was moved
ahead of the portal, because the `transcripts/` deliverable needs a one-shot runner
and not a web interface. That is the largest derisking step in the plan.

### 2026-08-19 — Documentation ownership

The analyst reviewed `AGENTS.md` and found it duplicating other documents. Moved
the content to its owner:

| Was in `AGENTS.md` | Now lives in |
|---|---|
| The hard rules | `plan.md` section 8, renamed IR1 to IR10 to avoid a clash with the risks R1 to R12 |
| The query traps | `plan.md` section 8, as a subsection referring to section 2 |
| The definition of done | `plan.md` section 9 |
| The scope-deviation procedure | `plan.md` section 10 |
| The commands | `README.md` |
| The layer table | `docs/structure.md` section 2, which already owned it |

`AGENTS.md` is now a router. It holds the read-first order, the drift checklist, the
writing style, and the conventions, and it duplicates nothing.

## Open items

| # | Item | Owner | Blocks |
|---|---|---|---|
| O1 | Approve the tier plan, and choose the landing point in `plan.md` section 5. | Daniel | Stage 2. |
| O3 | Confirm `OCEAN_ANTHROPIC_KEY` reaches Haiku 4.5. Unverified by request. | Daniel | Stage 6. |

Closed: **O2**, the OpenAI gateway `base_url`. ADR-005 dropped the OpenAI path, so
the question no longer applies.

## Deviations from the plan

| # | Deviation | Record |
|---|---|---|
| V1 | Ray runs Claude Haiku 4.5, not `gpt-5.6-luna` as the brief specifies. | ADR-005, risk R1, criterion 31. Disclosed in `NOTES.md`. |
| V2 | The implementation estimate exceeds the brief's 3-hour budget. | `plan.md` section 5, risk R2. Three cut lines, and the analyst chooses where to stop. |

### 2026-08-19 — Stages 2, 3, 5, and memory: two real defects found

Built the foundation directly, then fanned out stages 3, 4, and 5 to three
subagents in isolated git worktrees. Wrote the shared contracts first —
`config.py`, `db.py`, `clock.py`, `schemas.py`, and `injection.py` — so the parallel
work touched disjoint files and merged without conflict.

**Defect 1: the grounding verifier could be defeated by its own input.** A citation
identifier is parsed out of model-authored answer text, so it is not trusted input.
The first implementation matched it with SQL `LIKE identifier || '%'`, where `_` and
`%` are wildcards. `[msg:%]` therefore matched every row and verified as a real
citation, and `[msg:________]` matched every 32-character id. The mechanism that
exists to prove Ray is not hallucinating could have been forged by Ray. Fixed with
`substr(column, 1, ?) = ?`, plus a guard rejecting any table not in
`db.READ_TABLES`, plus `test_sql_wildcard_identifiers_do_not_forge_a_pass`. Recorded
as query trap 5 in `plan.md` section 8.

**Defect 2: absent values are `NULL`, not empty strings.** `plan.md` claimed in three
places that `campaign_id` and `attack_type` hold `''` when absent, and that
`IS NOT NULL` therefore fails to filter them. The opposite is true:

```
SELECT typeof(campaign_id), COUNT(*) FROM messages GROUP BY 1;   -- null 2274, text 14
SELECT COUNT(*) FROM messages WHERE campaign_id = '';            -- 0
```

The same holds for `override_reason`, `overridden_by`, and `links.scan_verdict`. The
claim came from reading sqlite3 CLI output, which renders `NULL` as blank. Any query
written as `campaign_id = ''` would have silently returned zero rows. Corrected in
`plan.md` 3.3 item 4 and section 8 trap 2, and in the campaign-correlator prompt.
Queries now use `COALESCE(column, '') <> ''`, which is correct either way.

Both defects were found by a subagent verifying its own work against the database
rather than trusting the instructions it was given. That is `plan.md` section 9 item
5 earning its place.

**Also hardened `injection.py`** for two reported gaps: an inline role marker not at
a line start, and a multi-word tool name in an exfiltration request. Still catches
all 6 planted messages with 0 false positives across all 2288.

**Worktree note:** the subagents did not commit inside their worktrees, so their
files were copied across by hand. Later fan-outs instruct them to commit.

### 2026-08-19 — Stages 9, 10, 11, and a portal defect the analyst found

Fanned out the three remaining stages to subagents in worktrees. All merged.

**Defect 3, reported by the analyst from the running portal.** Asking a question in
the interface returned `SyntaxError: Unexpected token 'I', "Internal S"... is not
valid JSON`. The server raised
`PydanticSerializationError: Unable to serialize unknown type: <class 'sqlite3.Connection'>`.

Root cause: three tool wrappers in `subagents.py` recorded their trace arguments with
`locals()`. **Inside a closure, `locals()` also returns the free variables the
function references**, so `ctx` — and with it the sqlite3 connection — entered the
tool-call log. `Turn.to_dict()` goes straight to the browser, so one unserializable
value turned every good answer into a 500.

The portal's own tests passed throughout, because they used a fake Ray whose tools
recorded nothing. The gap was between two correct components.

Two fixes, because the leak and the fragility are separate problems:

1. `find_messages`, `find_users`, and `recall` now build their argument dictionaries
   explicitly. No `locals()` remains anywhere in `src/ray/`.
2. `trace.json_safe` coerces anything unexpected to its repr, and every path into a
   trace passes through it. A trace records what happened; it must never be the
   reason a good answer fails to reach the analyst.

`tests/test_trace_serialization.py` closes both halves: `json_safe` tolerates a
connection, and a test drives **every registered tool through the real wrappers** and
asserts each recorded argument is a scalar. A further test fails if the registry gains
a tool that the serialization test does not cover.

**Stage 10, the compiled adjudicator, finished inside its 35-minute timebox** with
real measured numbers on Haiku:

| Program | Agreement | Adversarial | Combined |
|---|---|---|---|
| Hand-written baseline | 0.625 | 0.688 | **0.6625** |
| DSPy `BootstrapFewShot` | 0.833 | 0.688 | **0.7458** |
| Constant `safe` predictor | high | **0.000** | far below both |

The adversarial half carries 60% of the combined score, above the 50% floor ADR-009
requires. The constant-`safe` result of 0.0 is asserted by a test, which is the
demonstration that a one-sided metric would have been fooled: agreement alone would
score that predictor above 98%.

The subagent also caught an honesty problem in its own artifact. `BootstrapFewShot`
adds few-shot demonstrations without rewriting instruction text, so the exported
`prompt` would have been byte-identical to the baseline while carrying a higher
`score`. It folded the three bootstrapped demonstrations into the exported prompt so
the artifact matches the number recorded beside it.

**Stage 11, the portal**, serves one self-contained page: no external script,
stylesheet, font, or CDN. Citation chips, the tool-call log, the entity graph as
inline SVG, and the memory confirm gate. Untrusted strings render through
`textContent` or a single escaping helper, because an answer can quote attacker text.

### 2026-08-19 — Defect 4, also reported by the analyst: a truncated evidence panel

The portal showed `Found 7 message(s) matching the filters.` above a table holding its
header and **one** row. The analyst saw one message where Ray had found seven.

Cause: `trace.MAX_PREVIEW` was 600 characters, and a seven-row message table exceeds
that. A second cap in `Turn.to_markdown` printed only the first 18 lines of a result,
so the saved transcripts were clipped the same way.

Both are **display limits only.** The model always received the tool's full text
through `ToolResult.render()`, so no answer was ever computed from truncated
evidence — this cost visibility, not correctness. That distinction matters, because
the evidence panel exists precisely so the analyst can check Ray's rows.

Fixes:
- `MAX_PREVIEW` raised to 24000, which clears `find_messages` at its default limit of
  50 rows.
- `MAX_PREVIEW_LINES` set to 400, and the markdown now states how many lines it
  dropped rather than ending silently.
- The portal's `.call-preview` scroll box raised from 220px to 560px.

A cap still exists in both places, so one pathological result cannot dominate a
transcript or the JSON payload.

Four new tests: every one of the seven flagged finance ids appears in the preview and
in the rendered markdown, a pathological result is still capped, and the markdown
reports what it dropped.

Both defects the analyst found were in the interface layer, and both were invisible to
the test suite because the portal tests used a fake Ray. The lesson recorded here: a
component test that fakes its collaborator proves the component, not the seam.

### 2026-08-19 — Defect 5: the subagents were never attributed, and barely called

The analyst asked for a badge showing when a specialist took part. Building it
uncovered that the feature it was meant to display did not work.

**Two separate faults.**

1. **Attribution was never wired.** `_emit` never passed a `subagent` value, so
   `ToolCall.subagent` was always None and `Turn.subagents_used` was always empty. The
   badge would have rendered nothing, forever. The cause was structural:
   `build_subagents` handed all three specialists the **same** tool objects from the
   main agent's registry, so a call carried no trace of its caller.

   Fixed by making attribution part of construction. `build_tools(ctx, subagent=...)`
   now returns a set tagged with that specialist's name, and `build_subagents` builds
   one tagged set per specialist. The main agent keeps the untagged set. A tool call
   is now attributable by construction rather than by convention.

2. **Haiku barely delegated.** None of the seven recorded transcripts contained a
   single delegation. The system prompt named the three specialists but gave no
   trigger for reaching them, and a small model does the work itself when it can.

   The prompt now lists concrete triggers per specialist and states that a matching
   trigger means `task` MUST be called before answering.

**Result after both fixes**, on the headline scenario: `auth-forensics` 4 calls and
`verdict-adjudicator` 4 calls, both attributed in the transcript and in the badge.

**Honest limit.** Delegation is model-driven — `deepagents` exposes a `task` tool and
the model decides. Haiku now delegates reliably on the verdict-adjudication trigger,
but still answers a scope question ("who else got hit by the campaign?") directly
instead of calling `campaign-correlator`. That is defensible, because `domain_intel`
and `entity_graph` already return the full picture, but it is not what the prompt
asks for. Tuning stopped here rather than chasing a small model further.

This matters for ADR-009: a compiled adjudicator prompt is worth nothing if the
adjudicator is never invoked. Before fix 2 it effectively was not.

### 2026-08-19 — Defect 6: a live API key reached four committed transcripts

Found by a repository-wide secret scan while verifying that a clean checkout works —
the last check before handover, and it should have been the first.

**Cause.** The `locals()` defect from defect 4 recorded `repr(RayContext)` into the
trace, and that repr contains `Config(api_key='sk-ant-…')`. Four transcripts recorded
before that fix carried a working Anthropic key, and so did four commits. The brief
says "Don't commit your API key." It was committed transitively, through a debugging
convenience that stringified a whole context object.

**Three layers now stand between a credential and a trace.** One would not be enough,
because the failure was not a missing check — it was a value travelling somewhere
nobody was looking.

1. **Source.** Tool arguments are built explicitly. No `locals()` remains in
   `src/ray`.
2. **Dataclass.** `Config.api_key` is declared `field(repr=False)`, so `repr(config)`
   cannot expose it even if a whole context is stringified again.
3. **Trace.** `trace.scrub` redacts credential shapes from every string entering a
   trace, applied inside `json_safe` and `_preview`. A transcript is a file that gets
   shared, so it gets the strictest treatment.

**Guards.** `repr(Config)` hides the key; `scrub` redacts the known shapes; a trace
handed a key discards it; and two tests fail the whole suite if any committed
transcript contains a credential or a `RayContext` repr. The fake key in the test is
assembled from string parts so that a repository-wide scan never has to whitelist a
test file.

**Remediation.** Transcripts 01, 02, 03, and 07 re-recorded with the fixed code. The
key purged from git history with `filter-branch`, the agent worktrees and their
branches removed, and reflogs expired with `gc --prune=now`. The real key fragment
returns nothing from `git rev-list --all`.

**The key still had to be rotated.** A history rewrite removes the object; it does not
undo the exposure. That is the analyst's action, and it was reported at handover.

**What this says about process.** Defects 4, 5, and 6 all descend from one line of
convenience code, and each surfaced in a different way: a 500 in the browser, a
truncated panel, and a leaked credential. The suite passed through all three. A secret
scan belongs in the definition of done, not in the final verification pass.
