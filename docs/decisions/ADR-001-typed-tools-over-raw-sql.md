# ADR-001: Typed parameterized tools instead of a raw SQL tool

**Date:** 2026-08-19
**Status:** accepted

## Context

Ray answers a natural-language question from a SQLite database. The brief sets a
hard requirement: every claim traces to a row, and Ray says so when the data does
not support an answer. That requirement is the main grading surface.

Two ways exist to give an agent access to the database. The agent writes SQL
against a general tool. Or the agent calls a narrow tool that already holds its
query.

The database also holds four traps that a general query misses. Message
`93bae03b` has an empty `campaign_id` although it belongs to the acme-portal
activity. `sender-reputation` ran on 2 messages only, so an absent result is not
a benign result. Two campaign members are recorded `safe` on an unscanned link.
A relative window that ends at `db_meta.data_as_of` drops rows.

## Decision

Ray reaches the database through nine typed parameterized tools. Each tool holds
its own SQL. Each tool returns typed rows that carry row identifiers.

Ray gets no general SQL tool.

A tool retrieves. A tool never reasons. ADR-008 puts reasoning in three subagents,
and it records why an earlier draft of this decision was wrong to place a verdict
behind a tool signature.

`grounding.py` checks the answer after the agent produces it. The check extracts
every citation and confirms that a row matches. The portal shows a warning for
any citation that no row matches.

## Alternatives Considered

**A single `run_sql` tool over a read-only connection.** This is faster to build
and it answers any question. Rejected for three reasons. The model writes the
join, so a wrong join returns a confident wrong answer. A citation becomes
optional, because the tool returns whatever the query selected. The schema must
enter the prompt, which spends context on a fixed cost.

**Typed tools plus a `run_sql` escape hatch.** Rejected as the primary design. An
agent prefers a general tool over a specific one, so the domain knowledge encoded
in the narrow tools decays and citation discipline decays with it.
`conversation.md` defers this as item F1.

## Consequences

**Positive.** Every query is reviewed and tested before the agent runs once. The
four traps above are handled in code, where a test asserts the behaviour, and not
in a prompt, where a model may ignore the instruction. The whole tool layer is
unit-testable with zero model calls, so no key is needed to deliver the graded
grounding requirement. Grounding becomes a verified property rather than a prompt
promise.

**Negative.** More code than a single tool. A question outside the tool set gets
no answer, and Ray must say that it cannot answer it. The tool count raises the
tool-schema token cost on every turn.

**Follow-up.** Keep every tool input flat and scalar, per risk R7. A nested object
in a tool signature risks rejection by the model.
