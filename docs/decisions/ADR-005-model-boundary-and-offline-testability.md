# ADR-005: Claude Haiku 4.5 as the model, with an offline-testable core

**Date:** 2026-08-19
**Status:** accepted
**Supersedes:** the OpenAI variant of this decision, taken earlier the same day.

## Context

The brief requires `deepagents`. The brief also states: "Use gpt-5.6-luna."

The OpenAI key issued for this task holds no credit, and the funding sits with the
issuing side rather than with this project. The substitution to Anthropic was
directed on that basis, and `OCEAN_ANTHROPIC_KEY` serves Claude Haiku 4.5.

Three further facts bear on the choice.

1. `deepagents` 0.7.7 declares `langchain-anthropic` as a dependency. It does not
   declare `langchain-openai`. An Anthropic model therefore needs no extra
   package, and an OpenAI model needs one.
2. `create_deep_agent` accepts `model: str | BaseChatModel | None`. Either
   provider wires in cleanly. This is verified, not assumed.
3. ADR-009 compiles a prompt with DSPy. An optimizer makes many model calls, so a
   cheap fast model changes whether that step is affordable at all.

## Decision

**Ray runs on Claude Haiku 4.5.** `config.py` reads `RAY_MODEL` and defaults to
`claude-haiku-4-5-20251001`. It reads `OCEAN_ANTHROPIC_KEY`. `agent.py` builds one
`ChatAnthropic` instance and passes it to `create_deep_agent`.

The project does not plan a re-record on `gpt-5.6-luna`. One model, committed to,
rather than work held behind a key that may stay unfunded.

**`NOTES.md` names the model Ray runs on**, in section 0, because a reader needs to
know what produced the recorded transcripts and why several prompt-level decisions
exist.

**The core stays offline-testable.** The data layer and the whole tool layer take
no model and make no network call. Every test runs with no key present.

DSPy reaches Anthropic through `litellm`, which reads `ANTHROPIC_API_KEY`. The
compile script copies `OCEAN_ANTHROPIC_KEY` into that variable at its own start.
Ray keeps one key in one environment variable.

## Alternatives Considered

**Hold every agent stage until the OpenAI key is funded.** Rejected because it
blocks every capability demonstration and the DSPy compile on funding this project
does not control, and the brief sets a 3-hour budget.

**Develop on Haiku, then re-record the final transcripts on `gpt-5.6-luna`.**
Considered and rejected. It duplicates the transcript work and leaves the submission
dependent on an uncertain event.

**Keep a switchable two-provider boundary.** Rejected as unused complexity. One
provider needs one code path. `RAY_MODEL` still isolates the model identifier, so
a change costs one environment variable.

## Consequences

**Positive.** Ray runs today. Haiku is fast and inexpensive, which makes the
ADR-009 optimizer loop practical rather than theoretical. The dependency list
shrinks, because `deepagents` already ships the Anthropic integration. Every test
stays deterministic and free.

**Negative.** Haiku is a small model, so tool-calling discipline and instruction
adherence need more care in the prompt than a larger model would, and the recorded
transcripts show a small model's citation habits. Risk R9 tracks this.

**Follow-up.** A startup check reports a clear message when `OCEAN_ANTHROPIC_KEY`
is absent, and it names the variable to set. `NOTES.md` section 0 names the model.
