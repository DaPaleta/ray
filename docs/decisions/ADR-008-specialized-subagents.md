# ADR-008: Three specialized subagents, for reasoning that a query cannot do

**Date:** 2026-08-19
**Status:** accepted, and amended by ADR-011 and ADR-013

ADR-011 raises the roster from three specialists to five, and it supplies the reasoning
task that each new role earns its place with. The layer rule in this record is unchanged:
reasoning belongs to a subagent, and retrieval belongs to a tool. Read "Three, and no
more" below as the decision this record made, not as the current roster.

## Context

The first design used one agent with 14 flat tools. `deepagents` accepts
`subagents=[...]` natively, and subagent delegation is a headline feature of the
harness that the brief requires. A flat design under-uses the stack.

Three questions in the database need judgement, not a row lookup.

1. **Authentication that passes but proves nothing.** Message `276266c0` passes
   SPF, DKIM, and DMARC, because the attacker owns `acme-robotics.com`. The
   `stage2` analyzer cleared the message on exactly that ground. A tool can return
   the three results. Deciding that a clean pass over a lookalike domain is
   evidence *against* the sender needs reasoning.
2. **Campaign membership without a campaign identifier.** Message `93bae03b`
   carries an empty `campaign_id` while it shares a link domain with 14 campaign
   members. Deciding that it belongs needs a judgement about which shared
   indicators are strong enough.
3. **Disagreeing with a recorded verdict.** Seven messages hold a verdict that the
   evidence does not support. Forming an independent verdict and stating where it
   diverges is the brief's stated bonus, and it is a reasoning task.

A tool that returned a verdict would be a model call hidden inside a function.
Making it a subagent makes the reasoning visible and separately promptable.

## Decision

Ray delegates to three subagents. Each one holds its own instructions and reaches
only the tools that it needs.

| Subagent | Question it answers | Key evidence |
|---|---|---|
| **auth-forensics** | Does the authentication result support the claimed sender? | SPF, DKIM, DMARC against `organization.primary_domain`, and the lookalike distance of the sender domain. |
| **campaign-correlator** | Which messages belong to the same activity? | Shared link domain, shared sender domain, shared subject, pretext sequence, and timing. Never `campaign_id` alone. |
| **verdict-reviewer** | What is the independent verdict, and does it diverge from the record? | The evidence bundle from `get_detection`, plus the memory records that apply. ADR-009 compiles this prompt. |

Three, and no more. Each one earns its place with a reasoning task from the
context section. A fourth subagent would need a fourth such task.

The subagents replace three tools from the first design: `sender_intel`,
`campaign_intel`, and `review_analyst_overrides`. Each of those was a tool that
performed reasoning, which is the wrong layer for it.

Every subagent obeys the rules in `AGENTS.md` section 3. A subagent cites rows, a
subagent reads body text only through the fencing tool, and no subagent writes to
the database.

## Alternatives Considered

**One agent with a flat tool set.** The first design. Rejected. It under-uses the
required harness, it puts reasoning inside tools where no prompt can address it,
and it gives the analyst no visible account of which specialist reached which
conclusion.

**A subagent for each question class in the brief.** Five subagents, one per
capability. Rejected. Capability 1 and capability 3 are retrieval, not reasoning,
so their subagents would only forward tool output and spend a delegation round
trip for nothing.

**A tool that returns an independent verdict.** Rejected. It hides a model call
inside a function signature, so the reasoning becomes untestable and unpromptable,
and ADR-009 would have nothing to compile.

## Consequences

**Positive.** Reasoning sits at the reasoning layer, so each specialist prompt can
be written and measured on its own. The tool count falls from 14 to 9. The
verdict-reviewer becomes one bounded module with labelled data behind it, which is what
makes ADR-009 possible. The portal can name which specialist produced which
finding, which serves the explainability goal.

**Negative.** Each delegation costs a round trip and context, so a question that
touches all three subagents is slower and more expensive than a flat design.
Haiku is a small model, so a subagent that receives vague instructions may return
prose instead of a decision. Risk R9 covers this.

**Follow-up.** Keep each subagent's tool set minimal. `auth-forensics` needs
`get_message` and `find_users` only, and it must not receive `get_message_body`.
