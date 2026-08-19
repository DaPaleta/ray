# ADR-002: The database opens read-only by construction

**Date:** 2026-08-19
**Status:** accepted

## Context

Ray reads attacker-controlled content. Six messages in the database hold
instruction-shaped text in `body_text`. One of them orders Ray to write to
memory. Another orders Ray to call a tool and to leak every executive email
address.

A prompt can tell Ray to refuse such an instruction. A prompt is not a guarantee.
An injection that defeats the prompt must still not be able to change the
evidence, because the database is the only source of truth. If body text can
alter a row, then the source of truth becomes attacker-controlled.

## Decision

`db.py` exposes two connection factories.

1. **The query connection.** It opens with the SQLite URI
   `file:<path>?mode=ro` and `uri=True`. Every one of the read tools uses it.
2. **The memory connection.** It opens read-write. It serves the `agent_memory`
   table only, and `memory.py` is the only module that may request it.

No other write path exists. Ray never modifies `messages`, `links`,
`analyzer_results`, `decisions`, `remediations`, or `users`.

## Alternatives Considered

**One read-write connection, with the prompt forbidding a write.** Rejected. The
protection then rests on model compliance, which an injection targets directly.

**A read-only database file, set through file permissions.** Rejected as the
primary mechanism. It depends on the checkout state and on the operating system,
so a fresh clone can silently lose the protection. The URI flag travels with the
code.

**A separate database file for memory.** Rejected. The brief states that the
supplied database is Ray's only source of truth, and `agent_memory` already exists
inside it with the columns that Ray needs. A second file would split the truth.

## Consequences

**Positive.** A write attempt through the query connection raises
`sqlite3.OperationalError`, so the guarantee is a property of the process rather
than of the prompt. The blast radius of a successful injection is bounded to
`agent_memory`, which ADR-003 then protects with a provenance rule and a
confirmation gate. Acceptance criterion 1 is testable in one assertion.

**Negative.** Two connection factories instead of one, which is a small amount of
extra code. The memory tools cannot share a connection with the read tools.

**Follow-up.** A test asserts that a write statement on the query connection
raises an error. This is acceptance criterion 1.
