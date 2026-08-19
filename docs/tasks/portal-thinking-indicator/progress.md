# Progress — a keepalive thinking indicator in the portal

**Last updated:** 2026-08-19. Implemented and verified.

## What changed

| File | Change |
|---|---|
| `src/ray/portal/app.py` | New `GET /api/progress`. Reads `Turn` attributes only. |
| `src/ray/portal/index.html` | Spinner, elapsed clock, live step line, lost-contact state. |
| `tests/test_portal.py` | Eight tests. Seven on the endpoint, one on the page wiring. |
| `docs/decisions/ADR-014-...md` | The decision, and the four rejected alternatives. |
| `docs/structure.md` | The `portal/app.py` line now names the progress endpoint. |

## The endpoint

`GET /api/progress` returns `alive`, `turn_count`, `started_at`, `steps`, and `done`.
It touches no connection and calls no `startup()`, because the agent holds the sqlite
connection in the threadpool worker that serves the ask. `ExplodingConnection` in
`test_progress_never_touches_the_database` fails the test if that ever changes.

## The page

One tick per second drives the clock, and every third tick polls. The clock reads the
wall clock rather than counting ticks, because a background tab throttles the
interval. `setPending(false)` stops both, and it runs in the `finally` block of the
submit handler, so neither leaks past the turn on the error path.

Four states, in the order the analyst sees them:

If the baseline read itself fails, the first poll that sees an unfinished turn adopts
`turn_count - 1`. Without that, a page whose baseline read hit a dead server would show
an empty step line for the whole turn even after the server came back.

| State | Text |
|---|---|
| The ask is sent, the turn has not registered yet | `starting the turn…` |
| The turn is running | `2 tool calls · last: get_detection · verdict-reviewer` |
| `done` on the wire, ask still open | `answer drafted — checking every citation against the database…` |
| The turn ended with an error | `the turn ended with an error — loading the trace…` |
| Two consecutive failed polls | `The portal has not answered the last N status checks. The turn may still be running — still waiting.` |

State 3 is the grounding tail. `ask` sets `turn.answer` before `_ground` runs, so the
turn reads finished while a model call may still be pending. No new tool call appears
in that window, so the clock carries liveness through it.

## Verification

No test calls a model (ADR-005). The four states above were also driven against a live
server, because a unit test cannot show that the poll and the turn interleave.

| Check | Result |
|---|---|
| `pytest -q` | 252 pass, no key. |
| Live turn, polled once a second | Steps grew `[]` → `find_messages` → `+ get_detection`, then `done` flipped in the tail. |
| Two questions in a row | Baseline read 1, the second turn reported 2. The first question's steps never appeared under the second. |
| Server killed mid-turn | The indicator switched to the lost-contact text on the second failed poll, and kept the turn open. |
| Baseline read failed | Forced to null in the harness: the first poll adopted the baseline and the step line started reporting at t+1s, instead of staying empty. |
| Reduced motion | `prefers-reduced-motion` stops both animations. The clock and the step line still update. |
| JS syntax | The inline script parses. |

The live checks ran the page's own script against a DOM stub and a fake Ray whose
`ask` sleeps between recorded calls, so the timings above are the real code's, not a
transcript of intent. The harness stays in the scratchpad; it needs a browser
automation dependency this repo does not carry to become a committed test.

## Notes for a reader

1. The step line reports what finished, never what is running. `subagents._emit`
   records a call when the tool returns, so the trace cannot support the other claim.
2. `turn_count` is the only turn identity the page needs. The endpoint reports the
   latest turn, and the page compares against the baseline it read before the ask.
3. The page makes one extra request per question, for that baseline.
