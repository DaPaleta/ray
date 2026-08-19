# Conversation — Portal Visibility

## 2026-08-19

**User:** Add four visibility tabs (Overview, Execution, Conversations & Decisions,
Deep Tech Dive), each with a side-panel docs chat. Also update NOTES.md and README.md.

**Decision:** Route the docs chat through a *separate* endpoint (`/api/docs-ask`)
rather than through `ray.ask`. The main agent carries a system prompt that requires
`[kind:id]` citations checked against the database; a docs question has no rows
behind it, so every answer would trigger a grounding-failure banner. A separate
endpoint with its own prompt avoids that, and the UI labels it clearly as ungrounded.
ADR-015 records the reasoning.

**Decision:** Tab content loaded dynamically from real files via `GET /api/docs/{key}`.
Hardcoding content in HTML violates the single-source-of-truth rule and creates drift
(CLAUDE.md checklist). The renderer is an inline JS markdown parser with table support.

**Decision:** Existing "Analyst" panel wrapped under a fifth tab rather than removed
or restructured, because `pollProgress`/`renderPending` reference `#pending-indicator`
by id and must stay in the DOM during a live ask.
