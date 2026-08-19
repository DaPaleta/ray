# ADR-014: Poll a progress endpoint while a turn runs

**Date:** 2026-08-19
**Status:** accepted

## Context

`POST /api/ask` is a blocking request. `agent.py` invokes the model, the model
calls tools, the grounding check runs, and a failed check costs one more model
call. A turn takes 30 seconds or more, and the analyst sees nothing move until
the whole turn returns. The portal showed one static line of text for that whole
window, so a live turn and a dead server looked exactly alike.

The analyst asked for a keepalive indication: something that says nothing is
broken while Ray thinks. A CSS animation alone does not answer that question,
because it keeps animating after the server dies.

Three facts constrain the design.

1. **The server already records progress.** `ray.ask` calls `session.start()`
   before it invokes the agent, and `subagents._emit` records every tool call on
   that turn as the tool returns. The trace grows during the turn.
2. **A sqlite connection is bound to the thread that opened it.** The agent holds
   the connection inside the threadpool worker that serves `POST /api/ask`. A
   status request arriving during the turn must not query the database, and must
   not call `ray.startup()`.
3. **`session.start()` runs inside the worker.** A status request can arrive
   before it, and it then sees the *previous*, finished turn.

## Decision

Add `GET /api/progress`. It reads `Turn` attributes only — no query, no
`startup()` — and returns `alive`, `turn_count`, `started_at`, the completed
`steps`, `done`, and `error`. The page polls it every three seconds while an ask is in
flight, and stops when the ask returns.

Four rules make the indication honest.

1. **The page reads `turn_count` before it sends the ask.** Until the count grows
   past that baseline, the indicator says `starting the turn…` and reports no
   steps. Without the baseline, the first poll of the second question renders the
   first question's tool calls as its progress. When that read fails — the server
   was unreachable at submit time — the first poll that sees an *unfinished* turn
   adopts `turn_count - 1` instead, because `ask` writes an answer or an error
   before it returns, so an unfinished turn can only be this one.
2. **A step is a completed tool call.** `record()` runs when the tool returns, so
   the page says `last: get_detection`, never `running get_detection…`. The
   trace does not support the second claim, and an unsupported claim is the one
   thing this project does not make (`docs/vision.md` section 1a, goal 1).
3. **`done` on the wire while the ask is still open means the tail.** `ask` sets
   `turn.answer` before `_ground` runs, so the page then says the answer is
   drafted and the citations are being checked. The elapsed clock carries
   liveness through that window, because no new tool call appears in it.
4. **A failed turn is not the tail.** `ask` writes a stand-in answer on the
   error path, so `done` alone cannot tell the two apart. `error` carries the
   difference, and the page says the turn ended with an error instead.
5. **A poll that stops answering is reported.** After two consecutive failures
   the indicator says the portal has not answered its last status checks, and
   that the turn may still be running. It never reports the turn as failed,
   because a failed poll is not evidence of that.

## Alternatives Considered

1. **A CSS spinner and nothing else.** Cheapest, and it is what the request
   could be read to ask for. Rejected as the whole answer: it spins just as
   happily when the server is dead, which is the case the analyst wants to
   detect. It is kept as one of the three signals, not as the only one.
2. **Stream the turn over SSE or a WebSocket.** Genuine push, no polling. It
   needs an async route, a per-turn event queue, and a callback threaded from
   `subagents._emit` back into the interface layer. That inverts the dependency
   the layer table in `docs/structure.md` section 4 sets, for a page that serves
   one analyst on the local host. Rejected as cost without a matching gain.
3. **Poll `/api/state`.** No new endpoint. Rejected on fact 2: `/api/state`
   calls `ray.startup()` and `tools/memory.recall`, so polling it during a turn
   touches the connection the agent is using from a second thread.
4. **Fake progress — a determinate bar, or a rotating list of plausible steps.**
   Reads best of any option and is the easiest to build. Rejected outright.
   Inventing a step Ray did not take is the same defect class as inventing a
   citation.

## Consequences

1. The analyst sees a spinner, an elapsed clock, and the last completed step, and
   is told when the portal stops answering.
2. The interface layer gains one endpoint that reads the trace. It still holds no
   query and no threat logic.
3. `GET /api/progress` reports the latest turn, not a named one. The page tells
   turns apart by `turn_count`; nothing else needs to.
4. Progress resolution is three seconds and one tool call. That is enough to show
   movement and it costs no model call.
5. The page makes one extra request per question, to read the baseline count
   before the ask.
