# Repository structure

**Status:** active
**Last updated:** 2026-08-19

This document owns the repository layout. Add a new directory or a new file
category here in the same change that creates it.

## 1. Tree

```
ray/
├── AGENTS.md                     Instructions for coding agents. Codex reads this file first.
├── README.md                     Tech stack, commands, environment variables.
├── NOTES.md                      Submitted design write-up. Written last.
├── requirements.txt              Pinned serving dependencies. One command runs Ray with these.
├── requirements-dev.txt          Build-time dependencies. Adds DSPy for the compile step.
├── .env.example                  Template for local environment variables. Holds no secret.
├── .gitignore                    Excludes the virtual environment, caches, and .env.
│
├── data/
│   └── ocean_home_task.db        The supplied SQLite database. Ray's only source of truth.
│
├── prompts/
│   └── adjudicator.compiled.json The DSPy build artifact. Committed. See ADR-009.
│
├── src/ray/
│   ├── __main__.py               Entry point. Starts the portal.
│   ├── config.py                 Environment variables and defaults.
│   ├── db.py                     Connection factory. Read-only by default.
│   ├── clock.py                  Resolves "data as of" and relative time windows.
│   ├── schemas.py                Typed inputs and outputs for every tool.
│   ├── injection.py              Detects instruction-shaped content in body text.
│   ├── grounding.py              Verifies that every citation matches a real row.
│   ├── prompts.py                The system prompt and the three subagent prompts.
│   ├── subagents.py              The three specialists. See ADR-008.
│   ├── agent.py                  Builds the deepagents agent and loads the compiled prompt.
│   ├── trace.py                  Records the tool-call log for a turn. Serves goal 3.
│   ├── tools/                    One module per tool family. See section 3.
│   ├── dspy/
│   │   ├── compile_adjudicator.py  Build-time only. Writes prompts/adjudicator.compiled.json.
│   │   └── metric.py               The two-sided metric and the two label sets. See ADR-009.
│   └── portal/
│       ├── app.py                FastAPI application. Serves the page and the ask endpoint.
│       └── index.html            The single-page portal. Self-contained. Renders the graph.
│
├── scripts/
│   └── record_transcripts.py     Records the transcripts/ deliverable reproducibly.
│                                 Uses a scratch database copy by default.
│
├── tests/                        Unit tests. No test calls a model.
│
├── transcripts/                  Saved runs. A submission deliverable.
│
└── docs/
    ├── vision.md                 Purpose, scope, terminology.
    ├── structure.md              This file.
    ├── home-task-brief.pdf       The original brief.
    ├── decisions/                Architecture decision records. ADR-NNN-short-title.md.
    └── tasks/<task-name>/
        ├── plan.md               Context, approach, scope, risks, acceptance criteria.
        ├── progress.md           Running implementation log.
        └── conversation.md       Decisions, questions, and analyst guidance.
```

## 2. Layer rules

Ray has four layers. A layer depends only on a layer below it.

| Layer | Modules | Rule |
|---|---|---|
| **Interface** | `portal/`, `__main__.py` | Holds no query and no threat logic. |
| **Agent** | `agent.py`, `subagents.py`, `prompts.py`, `trace.py` | Holds no SQL. Reaches the data only through a tool. |
| **Tools** | `tools/`, `schemas.py`, `injection.py`, `grounding.py` | Holds every query. Returns typed rows with citations. |
| **Data** | `db.py`, `clock.py`, `config.py` | Holds the connection and the time resolution. |

`src/ray/dspy/` sits outside the four layers. It runs at build time only. Nothing
in the serving path imports it. ADR-009 records the reason.

## 3. Tool modules

Each module in `src/ray/tools/` holds one tool family. Nine tools in total.

| Module | Tools |
|---|---|
| `messages.py` | `find_messages`, `get_message`, `get_message_body` |
| `detection.py` | `get_detection` |
| `intel.py` | `domain_intel`, `entity_graph` |
| `people.py` | `find_users` |
| `exposure.py` | `blast_radius` |
| `memory.py` | `remember`, `recall`, `watchlist_sweep` |

`get_detection` returns the analyzer results, the decision, and the remediation for
one message in one call. The three are always needed together, so one call
replaces three.

Three tools from the first design are gone. `sender_intel`, `campaign_intel`, and
`review_analyst_overrides` each performed reasoning, which belongs at the agent
layer. ADR-008 makes them subagents.

## 3a. Subagents

`src/ray/subagents.py` holds three specialists. Each one reasons. None retrieves
on its own account beyond the tools listed.

| Subagent | Tools it may reach |
|---|---|
| `auth-forensics` | `get_message`, `find_users`, `domain_intel` |
| `campaign-correlator` | `find_messages`, `domain_intel`, `entity_graph` |
| `verdict-adjudicator` | `get_detection`, `get_message_body`, `recall` |

`auth-forensics` must not receive `get_message_body`. It reasons about headers and
authentication only, so untrusted content has no place in its context.

## 4. File conventions

1. File names use kebab-case. Python module names use snake_case, because the
   Python import system requires it.
2. Branch names use flat kebab-case.
3. Commit messages follow Conventional Commits.
4. A test file matches the module that it covers: `tests/test_<module>.py`.
5. A transcript file uses the pattern `transcripts/NN-<short-title>.md`.

## 5. Excluded from version control

`.gitignore` excludes the following. Never commit any of them.

1. `.env` and every file that holds a key.
2. `.venv/` and every virtual environment.
3. `__pycache__/`, `.pytest_cache/`, `*.pyc`.

`data/ocean_home_task.db` **is** committed. ADR-006 records the reason.
