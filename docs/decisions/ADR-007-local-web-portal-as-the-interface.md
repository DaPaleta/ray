# ADR-007: A local web portal is the analyst interface

**Date:** 2026-08-19
**Status:** accepted

## Context

The brief places Ray inside a security portal. The analyst asked for a minimalist
interface that stays open for the whole session.

Capability 4 needs more than one turn. The analyst states the CFO policy on one
turn. Ray applies the policy on a later turn. Acceptance criterion 13 requires
this, so the interface must hold a session across turns.

Capability 5b needs a confirmation control. ADR-003 rule 2 requires the analyst to
confirm a proposed memory record before Ray writes it. A plain text stream has no
place to put that control.

The brief also sets a 3-hour budget, so the interface competes with the
investigation quality for time.

## Decision

Build a local web portal. FastAPI serves one self-contained HTML page from
`src/ray/portal/`. `python -m ray` starts the server, and the analyst opens the
page in a browser tab that stays open for the session.

The page holds four regions.

1. The conversation.
2. The evidence for the current answer, with each citation as a row reference.
3. The active memory records.
4. The pending memory proposals, each with a confirm control and a reject control.

The server keeps one session. A `deepagents` checkpointer holds the conversation
state, so a later turn sees an earlier turn.

The page is self-contained. It loads no external script, no external stylesheet,
and no remote font.

## Alternatives Considered

**A Rich terminal session.** The cheapest option, at roughly 20 minutes. Rejected
by the analyst in favour of the portal. It also renders the confirmation control
and the evidence table less well than a page does.

**A full Textual multi-pane interface.** Rejected. It is the most expensive of the
three, and it spends budget on presentation rather than on investigation quality.

**A one-shot command only.** Rejected. It cannot demonstrate the capability 4
memory loop across turns, which is the strongest single result in the plan.

## Consequences

**Positive.** The session persists, so the capability 4 demonstration works. The
evidence region makes grounding visible, and the grounding warning from
`plan.md` 4.6 has a natural place to appear. The confirmation control makes the
ADR-003 gate real rather than notional. The result matches the security-portal
framing in the brief.

**Negative.** It costs roughly 40 minutes of a 3-hour budget, which is the largest
single interface cost of the three options. It adds `fastapi` and `uvicorn` as
dependencies. Risk R2 therefore names the portal as the first thing to reduce to a
plain form, ahead of cutting any tool.

**Follow-up.** `plan.md` section 5 places the portal at stage 7, after the tools
and after the agent. The portal holds no query and no threat logic, per
`docs/structure.md` section 2.
