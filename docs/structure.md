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
├── NOTES.md                      Submitted design write-up. Start here.
├── requirements.txt              Pinned serving dependencies. One command runs Ray with these.
├── requirements-dev.txt          Build-time dependencies. Adds DSPy for the compile step.
├── .env.example                  Template for local environment variables. Holds no secret.
├── .gitignore                    Excludes the virtual environment, caches, and .env.
│
├── data/
│   └── ocean_home_task.db        The supplied SQLite database. Ray's only source of truth.
│
├── prompts/
│   ├── reviewer.compiled.json The verdict-reviewer DSPy artifact. Committed. See ADR-009, ADR-013.
│   ├── reviewer.report.md     Its before-and-after compile report.
│   ├── correlator.compiled.json  The campaign-correlator DSPy artifact. Committed. See ADR-012.
│   └── correlator.report.md      Its report, with the three shortcut baselines.
│
├── src/ray/
│   ├── __main__.py               Entry point. Starts the portal.
│   ├── config.py                 Environment variables and defaults.
│   ├── db.py                     Connection factory. Read-only by default.
│   ├── clock.py                  Resolves "data as of" and relative time windows.
│   ├── schemas.py                Typed inputs and outputs for every tool.
│   ├── injection.py              Detects instruction-shaped content in body text.
│   ├── grounding.py              Verifies that every citation matches a real row.
│   ├── prompts.py                The system prompt and the five specialist prompts.
│   ├── subagents.py              The five specialists. See ADR-008 and ADR-011.
│   ├── agent.py                  Builds the deepagents agent and loads the compiled prompt.
│   ├── trace.py                  Records the tool-call log for a turn. Serves goal 3.
│   ├── tools/                    One module per tool family. See section 3.
│   ├── dspy/
│   │   ├── compile_reviewer.py  Build-time only. Writes prompts/reviewer.compiled.json.
│   │   ├── compile_correlator.py   Build-time only. Writes prompts/correlator.compiled.json.
│   │   ├── metric.py               The verdict metric and its two label sets. See ADR-009.
│   │   └── correlation.py          The set metric, the seeds, and the three shortcut baselines. See ADR-012.
│   └── portal/
│       ├── app.py                FastAPI application. Serves the page, the ask endpoint,
│       │                         the progress poll, and the docs endpoints (ADR-015).
│       └── index.html            The single-page portal. Self-contained. Five tabs:
│                                 Overview, Execution, Conversations & Decisions,
│                                 Deep Tech Dive, and Analyst (live interrogation).
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
    └── tasks/<task-name>/          ray-email-threat-investigator, ray-soc-role-subagents,
                                    portal-thinking-indicator, portal-visibility.
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
| `memory.py` | `remember`, `recall` |
| `watchlist.py` | `watchlist_sweep`, `extract_indicators` |

`get_detection` returns the analyzer results, the decision, and the remediation for
one message in one call. The three are always needed together, so one call
replaces three.

Three tools from the first design are gone. `sender_intel`, `campaign_intel`, and
`review_analyst_overrides` each performed reasoning, which belongs at the agent
layer. ADR-008 makes them subagents.

## 3a. Subagents

`src/ray/subagents.py` holds five specialists, in the three tiers a SOC runs. Each one
reasons. None retrieves on its own account beyond the tools listed. ADR-008 set the
layer rule, and ADR-011 set this roster.

| Tier | Subagent | Tools it may reach |
|---|---|---|
| Triage | `triage-officer` | `find_messages`, `get_detection`, `watchlist_sweep`, `recall` |
| Investigation | `auth-forensics` | `get_message`, `find_users`, `domain_intel` |
| Investigation | `campaign-correlator` | `find_messages`, `domain_intel`, `entity_graph` |
| Investigation | `verdict-reviewer` | `get_detection`, `get_message`, `get_message_body`, `recall` |
| Response | `incident-responder` | `blast_radius`, `get_detection`, `find_users`, `recall` |

**Only `verdict-reviewer` reaches `get_message_body`.** A pretext is evidence for a
verdict, so it needs the wording. Three of the other four are excluded by decision:
`auth-forensics` reasons about headers, `triage-officer` orders recorded fields, and
`incident-responder` works from exposure rows. `campaign-correlator` works over
indicators, so a body would only widen an already wide context.
`subagents.NO_BODY_ACCESS` holds the set, and a test asserts it against the table
above.

Two prompts are compiled, one artifact per specialist under `prompts/`:
`verdict-reviewer` (ADR-009) and `campaign-correlator` (ADR-012). The other three
stay hand-written, because the database holds no label for a priority order, a
response plan, or an authentication judgement that the prompt's own rule does not
already state.

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
