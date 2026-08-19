# Progress — Ray, the email-threat investigator agent

**Task:** `docs/tasks/ray-email-threat-investigator/`
**Plan:** `plan.md` section 5 owns the stage list.

---

## Current state — read this first

*This section is the answer to "what is done, how do I run it, and how do I request a
change". It is updated at the end of every stage.*

**Last updated:** stages 2, 3, 5, and the memory half of 6 are complete. **108 tests
pass, and none needs an API key.**

### What works right now

| Capability | State | How it is proven |
|---|---|---|
| Configuration and defaults | working | 5 tests |
| Read-only database access | working | 4 tests, one per write verb |
| Time-window resolution, both traps closed | working | 7 tests, including the 38-versus-41 trap |
| Prompt-injection detection | working | All 6 planted messages caught, **0 false positives across all 2288** |
| Grounding verification | working | 23 tests, including citation forgery by SQL wildcard |
| `find_messages`, `get_message`, `get_message_body` | working | 28 tests in `test_core_tools.py` |
| `get_detection` | working | Same suite. Reports the analyzers that did **not** run |
| Memory: `remember`, `recall`, provenance, confirm gate | working | 19 tests. The poison payload is refused |
| `domain_intel`, `entity_graph`, `find_users` | in progress | stage 4, running in a worktree |
| Agent, subagents, prompts, one-shot runner | written, untested | needs stage 4 to merge, then a live run |
| Blast radius, watchlist sweep | not built | stage 9 |
| DSPy compiled prompt | not built | stage 10 |
| Portal, graph, trace rendering | `trace.py` works; portal not built | stage 11 |

### How to run what is built

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q                  # 108 tests, no key needed
python -m ray --check      # readiness report, calls no model
```

Ray cannot yet answer a question end to end. That needs stage 4 merged and one live
run. Once it can:

```bash
export OCEAN_ANTHROPIC_KEY=...
python -m ray --ask "Anything targeting our finance team this week?"
python -m ray                                  # the portal, after stage 11
```

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
| 1 | 8 | Write-up | not started |
| 2 | 9 | Capability 5a and 5b | **done** |
| 2 | 10 | DSPy compile | not started |
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
