# Plan — a keepalive thinking indicator in the portal

**Status:** implemented. See `progress.md`.
**Created:** 2026-08-19
**Owner:** Daniel Goren
**Jira ticket:** none. This continues the external home assignment, not Evinced work,
which matches `docs/tasks/ray-soc-role-subagents/plan.md`.

This document uses Simplified Technical English. `docs/vision.md` section 3 owns the
terminology. Implementation rules IR1 to IR10 in
`docs/tasks/ray-email-threat-investigator/plan.md` section 8 still bind this work.

## 1. Context

The analyst asked for a keepalive loader in the portal, so that a wait does not look
like a fault.

`POST /api/ask` blocks for the whole turn: the model call, every tool call, the
grounding check, and one corrective re-cite when the check fails. That is 30 seconds
or more. The portal showed one static line — "Ray is investigating… a turn can take
30 seconds or more" — for the entire window. A live turn and a dead server looked the
same.

This is interface work only. No tool, no prompt, and no query changes.

### 1.1 Scope deviation, recorded

The active task when this arrived was `docs/tasks/ray-soc-role-subagents/`, which is
implemented. This request touches `portal/` and no part of that plan, so it gets its
own task folder rather than an amendment to that one.

## 2. Approach

Three signals, because each one fails in a different way.

| Signal | What it proves | How it fails alone |
|---|---|---|
| Spinner | The page is alive. | It spins after the server dies. |
| Elapsed clock | The turn is alive from the page's side. | It counts up against a dead server too. |
| A poll of `GET /api/progress` | The server is alive, and the turn is moving. | It needs the endpoint. |

ADR-014 holds the decision and the three alternatives that were rejected: a spinner
alone, an SSE stream, and polling `/api/state`.

### 2.1 The one hard constraint

A poll arrives while the agent holds the sqlite connection in a threadpool worker. A
connection is bound to the thread that opened it, so `GET /api/progress` reads `Turn`
attributes only. It runs no query and it never calls `ray.startup()`.
`test_progress_never_touches_the_database` enforces this.

### 2.2 The one race

`ray.ask` calls `session.start()` inside the worker, so a poll can land before the
turn exists and see the previous, finished turn. The page therefore reads
`turn_count` **before** it sends the ask, and reports no step until the count grows
past that baseline.

## 3. Honesty rules

`docs/vision.md` section 1a goal 1 binds this indicator as much as an answer.

1. A step is a **completed** tool call. `record()` runs when a tool returns, so the
   page says `last: get_detection` and never `running get_detection…`.
2. No fake progress. No determinate bar over an unknown duration, and no rotating
   list of steps Ray did not take.
3. A failed poll is reported as a failed poll. The indicator says the portal has not
   answered its last status checks and that the turn may still be running. It never
   reports the turn as failed.

## 4. Out of scope

1. **A push channel.** ADR-014 alternative 2.
2. **Per-tool timing, or a token counter.** The trace holds no timing per call, and
   adding it belongs to the trace layer, not here.
3. **Cancelling a turn.** No cancel path exists in `agent.py`, and inventing one is
   a separate task.

## 5. Acceptance criteria

1. While a turn runs, the indicator shows a spinner, an elapsed clock, and the last
   completed tool call with the specialist that made it.
2. On the second question of a session, the first poll never renders the first
   question's tool calls.
3. `GET /api/progress` performs no query and calls no `startup()`.
4. When the server stops answering, the indicator says so, and does not claim the
   turn failed.
5. A reduced-motion reader loses no information.
6. `pytest` passes, with no key.
