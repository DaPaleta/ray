# Conversation — a keepalive thinking indicator in the portal

## 2026-08-19 — the request

> "please add a keepalive loader indication while ray is thinking, so the user knows
> nothing is broken as he waits for a response in the portal."

## Decisions

1. **A spinner alone is not the answer.** The word in the request is *keepalive*. An
   animation keeps animating when the server is dead, which is the case the analyst
   wants to detect. The indicator therefore polls the server, and reports it when the
   poll stops answering. ADR-014 records this.
2. **A new endpoint, not `/api/state`.** `/api/state` calls `ray.startup()` and
   `tools/memory.recall`. Polling it during a turn would touch the sqlite connection
   the agent holds in another thread. `GET /api/progress` reads `Turn` attributes
   only.
3. **Real steps, or no steps.** The step line reports completed tool calls, because
   that is what the trace records. No determinate progress bar over an unknown
   duration, and no invented step list. Inventing a step is the same defect class as
   inventing a citation.
4. **Its own task folder.** The active task, `ray-soc-role-subagents`, is implemented
   and this touches none of its plan. Recorded in `plan.md` section 1.1. No Jira
   ticket, which matches that task's own note.

## Questions raised and answered

| Question | Answer |
|---|---|
| Can the page label the running tool? | No. `record()` fires when a tool returns, so only completed calls exist. The label says `last:`. |
| Why does the step line freeze near the end of a long turn? | The grounding tail. `turn.answer` is set before `_ground`, so the page reports the answer as drafted and the citations as being checked, and the clock carries liveness. |
| Why read the turn count before the ask? | `ray.ask` calls `session.start()` inside the threadpool worker. A poll that lands first sees the previous turn, and its steps would render as this turn's progress. |

## Observed during this work, not acted on

Two peer sessions were editing this repository at the same time. One of them wrote
`docs/tasks/ray-soc-role-subagents/progress.md` while this task was in flight, and its
verification table there attributes `test_progress_never_touches_the_database` and the
251-test count to the specialist rename. Both belong to this task. Left as found,
because that log is another task's, and reported to the analyst instead.
