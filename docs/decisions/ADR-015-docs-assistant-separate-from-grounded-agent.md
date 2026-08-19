# ADR-015: Docs assistant scoped separately from the grounded agent

**Date:** 2026-08-19  
**Status:** accepted

## Context

The portal visibility tabs each include a side-panel chat. The natural shortcut is to
route that chat through `ray.ask()`, since the full agent is already wired up.

## Decision

The docs assistant is a separate endpoint (`POST /api/docs-ask`) that calls the
Anthropic API directly with a fixed set of doc files and a lightweight prompt. It does
not use `ray.ask()`, the DB tools, or the grounding verifier.

The UI labels it explicitly: "Docs assistant — answers from repo files, no database
citation check."

## Alternatives Considered

**Route through `ray.ask`.** Rejected. The main agent's system prompt requires every
claim to carry a `[kind:id]` citation, and `grounding.py` re-checks every citation
against the database after the answer is written. A docs question ("what is DSPy
used for here?") has no rows behind it. Every answer would render a grounding-failure
banner, implying the DB-citation mechanism is broken when it is not.

## Consequences

- A second model path exists in the portal. It is clearly scoped: read-only, no DB,
  no grounding pass, no citation requirement.
- NOTES.md principle 1 ("the database is the only source of truth") continues to
  describe the main agent path. The docs assistant is labelled as different.
- `create_app(ray)` still constructs with no API key; the key is read inside the
  handler. Tests that exercise the no-key path receive a clear 503 instead of a 500.
