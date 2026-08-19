# ADR-010: A watchlist sweep, not a real-time alert feed

**Date:** 2026-08-19
**Status:** accepted

## Context

The analyst proposed real-time event reports from the analyst agents, as an
agentic initiative alongside the self-learning loop and remediation
recommendations.

The database does not support it. `messages.received_at` is a fixed column in a
static file. No table appends, no process writes a message, and no event stream
exists. The window closed at `2026-08-16T17:10:57Z`.

A live-looking feed would therefore replay stored timestamps as if they were
arriving now. That conflicts with the project's first principle: the database is
the only source of truth, and Ray states no fact that a row does not support. A
simulated arrival time is a fact that no row supports.

The underlying intent is sound, and it does not need simulation. The analyst wants
Ray to act on what it has learned, rather than only to answer what it was asked.

## Decision

**Ray keeps no alert feed. Ray keeps a watchlist.**

1. A memory record of kind `watch` holds an indicator and the reason to watch it.
   The learning loop proposes such a record, and the analyst confirms it under the
   ADR-003 gate.
2. The `watchlist_sweep` operation applies every `watch` record across the corpus
   and reports what matches. It reports each match with its citation, its
   remediation state, and the memory record that caught it.
3. A sweep runs when the analyst asks for it, and at the start of a session. It
   reports "no new match" when nothing matches, which is a real result.
4. Every match feeds the remediation recommendation, so the chain runs from a
   learned fact to a proposed action.

The demonstration is concrete. Ray reads the override trail whose stated reasons
decay to `Assuming same as the others.`, proposes a `watch` record on
`quaystone-billing-portal.com`, and the analyst confirms it. A later sweep returns
the five released messages, with the note that one phone confirmation covers the
first message only.

## Alternatives Considered

**A simulated live feed that replays `received_at`.** Rejected. It is the single
change in the plan that would make Ray state an unsupported fact, and it
contradicts the primary goal of a data-centered agent. A reader who checks the
schema finds no event source.

**A file watcher or a polling loop over the database.** Rejected. Nothing writes
to the database, so the loop would report nothing forever, and it would spend
budget on infrastructure with no output.

**Drop the initiative entirely and spend the time on the visualization.**
Considered and rejected by the analyst. The watchlist is cheap, because it reuses
the ADR-003 memory substrate and the existing query tools, and it is the only part
of the plan where Ray acts on its own learning.

## Consequences

**Positive.** Ray acts on learned knowledge, which satisfies the agentic-initiative
goal, and it fabricates nothing. The mechanism reuses the memory table and the
existing tools, so the cost is small. A sweep is deterministic and therefore
testable, which an event feed would not be. The chain from a learned fact to a
recommended action is visible end to end.

**Negative.** A sweep is pull, not push, so the demonstration is less immediately
striking than a live panel. The result depends on the analyst confirming a record
first, so a cold session has an empty watchlist and nothing to show.

**Follow-up.** Seed no watchlist record in the repository. An empty
`agent_memory` at checkout is the honest starting state, and the transcript shows
the record being proposed, confirmed, and then applied.
