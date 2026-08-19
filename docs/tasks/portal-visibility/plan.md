# Task — Portal Visibility

**Status:** in progress  
**Created:** 2026-08-19

## Goal

Add four presentation tabs to the analyst portal so a reviewer can understand the
project without reading raw markdown. Each tab pairs a rendered view of real repo
files with a side-panel docs assistant that answers questions from those files.

## Tabs

| Tab | Main content | Docs context |
|---|---|---|
| Overview | Architecture SVG, core features, design principles | vision.md, NOTES.md §1-2, key ADRs |
| Execution | Results from all 8 recorded transcripts | transcripts/, vision.md §4.1 |
| Conversations & Decisions | Rendered conversation.md files, ADR summaries | docs/tasks/*/conversation.md, docs/decisions/ |
| Deep Tech Dive | Tools list, subagent roster, DSPy story, message flow | NOTES.md §3, ADR-008/009/011/012 |

The existing "Analyst" panel stays as a fifth tab (the live interrogation interface).

## Approach

1. New `GET /api/docs/{key}` endpoint — returns the markdown text for a named doc
   set. The mapping is a dict of explicit relative paths in `app.py`; no path
   parameter is accepted to prevent traversal.
2. New `POST /api/docs-ask` endpoint — reads the same doc sets and calls the
   Anthropic API directly (no DB tools, no grounding pass). Returns a plain text
   answer. Labels itself in the UI as ungrounded.
3. `index.html` rewritten with tab navigation and four new tab bodies. Existing
   panels wrapped under "Analyst" tab. No id clashes; `pollProgress`/`renderPending`
   reach `#pending-indicator` by id as before.
4. A compact inline markdown renderer (no CDN) supports `##`, `**bold**`, tables,
   code blocks, and bullet lists — enough for the docs content.

## Constraints

- `create_app(ray)` must still construct with no key (tests pass with no env).
  The key is read inside the handler, not at construction time.
- No new top-level imports inside `create_app` — keep the seam testable.
- ADR-015 records the second assistant and why it is scoped separately.
- `docs/structure.md` updated for any new file categories.

## Acceptance

- Four new tabs render content loaded from real repo files.
- Side panel chat returns a reasonable answer to "what is DSPy used for here?".
- `pytest -q` still passes with no key.
- NOTES.md and README.md updated.
