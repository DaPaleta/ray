# Ray — an email-threat investigator agent

Ray is an investigator agent inside a security portal. A SOC analyst asks Ray a
question in natural language. Ray answers it from the organization's email data.

Detection ran before Ray. Analyzers scored every message, and a verdict exists for
every message. Ray explains what happened, why it happened, and what to do next.
Ray can also form its own verdict and disagree with the recorded one.

The organization is Acme Robotics. The primary domain is `acme.com`.

## Status

Complete and working. **201 tests pass with no API key**, 11 tools, 3 specialist
subagents, 7 recorded transcripts, and a compiled adjudicator prompt.

`NOTES.md` is the submission write-up and the best place to start.
`docs/tasks/ray-email-threat-investigator/progress.md` opens with a "Current state"
section covering what works, how to run it, and how to request a change.

## Quick start

```bash
git clone <repository-url> && cd ray

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then set OCEAN_ANTHROPIC_KEY in .env

python -m ray
```

The portal opens on `http://127.0.0.1:8765`. Keep the tab open for the session,
because Ray holds the conversation state across turns.

The database ships with the repository, so no data setup is needed.

## Commands

| Command | Purpose | Needs a key |
|---|---|---|
| `python -m ray` | Start the portal. | yes |
| `python -m ray --ask "…"` | Answer one question and write a transcript. | yes |
| `pytest` | Run every test. | no |
| `pytest -k tools` | Run the tool tests only. | no |
| `python -m ray.dspy.compile_adjudicator` | Build step. Recompiles the adjudicator prompt. Needs `requirements-dev.txt`. | yes |
| `python -m ray.dspy.compile_adjudicator --dry-run` | Builds the label sets and prints their sizes. Calls no model. | no |
| `python scripts/record_transcripts.py --list` | List the recorded scenarios. | no |
| `python scripts/record_transcripts.py 4` | Re-record one scenario. Uses a scratch database copy. | yes |

No test calls a model. The data layer and the tool layer are therefore testable
with no key present. See ADR-005.

The build step is optional. `prompts/adjudicator.compiled.json` is committed, so a
reviewer never needs to run it. See ADR-009.

## Environment variables

`.env.example` is the template. Copy it to `.env`, which `.gitignore` excludes.

| Variable | Default | Purpose |
|---|---|---|
| `OCEAN_ANTHROPIC_KEY` | *(none)* | Required to run the agent. Never commit it. |
| `RAY_MODEL` | `claude-haiku-4-5-20251001` | The model identifier. |
| `RAY_DB_PATH` | `data/ocean_home_task.db` | Path to the SQLite database. |
| `RAY_COMPILED_PROMPT` | `prompts/adjudicator.compiled.json` | The compiled adjudicator prompt. Ray falls back to the hand-written prompt when it is absent. |
| `RAY_HOST` | `127.0.0.1` | Portal bind address. |
| `RAY_PORT` | `8765` | Portal port. |

## Tech stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11 or later | `deepagents` requires it. The brief requires it. |
| Agent harness | `deepagents` 0.7.7 | The brief requires it. Ray uses its native subagent delegation. |
| Model | Claude Haiku 4.5, through `langchain-anthropic` | The issued OpenAI key never received credit. See the note below and ADR-005. |
| Reasoning | Three specialized subagents | ADR-008. |
| Prompt engineering | DSPy, at build time only | ADR-009. The serving path loads a static artifact. |
| Data | SQLite, through the standard library `sqlite3` | The supplied database. No ORM is needed for a read-only workload. |
| Interface | FastAPI and one self-contained HTML page | ADR-007. |
| Tests | `pytest` | No test calls a model. |

### Model substitution

The brief specifies `gpt-5.6-luna`. **Ray runs Claude Haiku 4.5 instead.** The
issued OpenAI key never received credit, so the project used the Anthropic key that
was available. `RAY_MODEL` isolates the identifier, so the change costs one
environment variable. ADR-005 records the decision and `NOTES.md` repeats it.

`deepagents` already ships `langchain-anthropic`, so this substitution removes a
dependency rather than adding one.

## What Ray handles

| # | Capability | Example question |
|---|---|---|
| 1 | Threat sweep | "Anything targeting our finance team this week?" |
| 2 | Verdict explanation | "Why is the message with the subject 'Action required: mailbox storage full' malicious?" |
| 3 | Indicator lookup | "I got an EDR alert that someone clicked a link on acme-portal.co. What do we know about it?" |
| 4 | Organizational memory | "Our CFO is Rachel Adler and she never sends wire requests over email. Remember that." |
| 5a | Blast-radius report, with a remediation recommendation | "Who else received this, which of those messages is still in an inbox, and what should I do?" |
| 5b | Watchlist loop | Ray proposes a watch record. The analyst confirms it. A later sweep applies it. |

Capabilities 5a and 5b are the two additions beyond the four required ones.
`NOTES.md` holds the argument for each.

Ray also forms an independent verdict and reports where it diverges from the
recorded one. Seven recorded verdicts in the database do not match their evidence.

The measured result of the compiled adjudicator prompt, against a two-sided metric
that a constant "safe" answer cannot game:

| Program | Agreement | Adversarial | Combined |
|---|---|---|---|
| Hand-written baseline | 0.625 | 0.688 | 0.6625 |
| DSPy `BootstrapFewShot` | 0.833 | 0.688 | **0.7458** |
| Constant `safe` | high | **0.000** | far below both |

`prompts/adjudicator.report.md` holds the report; ADR-009 explains the metric.

## How Ray reasons

Three specialized subagents handle the questions that a query cannot answer. See
ADR-008.

| Subagent | Question | The case it cracks |
|---|---|---|
| `auth-forensics` | Does the authentication result support the claimed sender? | A fake-CFO wire request that passes SPF, DKIM, and DMARC, because the attacker owns the lookalike domain. |
| `campaign-correlator` | Which messages belong to the same activity? | A phishing message that carries no `campaign_id` but shares a link domain with 14 campaign members. |
| `verdict-adjudicator` | What is the independent verdict, and does it diverge? | Seven recorded verdicts that the evidence does not support. |

The adjudicator prompt is compiled with DSPy against the database, and measured
against a two-sided metric: agreement with the 2288 recorded decisions, and correct
disagreement on 8 held-out rows whose recorded verdict is wrong. A one-sided metric
would score a constant "safe" answer above 98 percent. `NOTES.md` reports the
before-and-after number. See ADR-009.

## Design guarantees

1. **Grounded.** Every claim cites a row. A post-check verifies each citation
   against the database, and the portal warns about any citation that no row
   matches.
2. **Read-only by construction.** The query connection opens with SQLite
   `mode=ro`. Attacker-controlled content cannot change the evidence. `agent_memory`
   is the one writable table. See ADR-002.
3. **Injection-resistant.** Body text reaches the model only through a tool that
   fences it as untrusted evidence, and Ray reports each injection attempt to the
   analyst as a finding. See ADR-004.
4. **Honest about gaps.** The database holds no click telemetry and no EDR
   telemetry. Ray says that it does not know, rather than guessing.
5. **No simulated data.** Nothing appends to the database, so Ray has no alert
   feed. It sweeps an analyst-confirmed watchlist instead. See ADR-010.

## Documentation

| Document | Owns |
|---|---|
| `docs/vision.md` | Purpose, scope, terminology, project goals. |
| `docs/structure.md` | Repository layout. |
| `docs/decisions/` | The ten architecture decision records. |
| `docs/tasks/ray-email-threat-investigator/` | Plan, progress log, conversation log. |
| `AGENTS.md` | Rules for a coding agent working in this repository. |
| `NOTES.md` | The submitted design write-up. **Start here.** |
| `docs/home-task-brief.pdf` | The original brief. |

## Security

Never commit a key. `.gitignore` excludes `.env`. `README.md` and `.env.example`
name every variable, and neither holds a value.

`data/ocean_home_task.db` is committed on purpose. It is synthetic data for a
fictional organization, and it holds no secret. See ADR-006.
