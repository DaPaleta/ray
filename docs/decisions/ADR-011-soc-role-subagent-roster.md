# ADR-011: Five subagents in the three tiers a SOC runs

**Date:** 2026-08-19
**Status:** accepted, and renamed by ADR-013 (`verdict-adjudicator` is now
`verdict-reviewer`)
**Amends:** ADR-008, which set the roster at three and stated that a fourth subagent
would need a fourth reasoning task. This record supplies two such tasks.

## Context

ADR-008 put reasoning at the reasoning layer and named three specialists. Each one
answers an investigation question. The roster is therefore an investigation tier and
nothing else.

A SOC does not consist of an investigation tier alone. Two other roles do work that
this project already needs, and each one holds a reasoning task that a query cannot
perform.

1. **Triage.** `docs/vision.md` capability 1 asks "anything targeting our finance team
   this week?". The answer is a queue, and a queue needs an order. The order is a
   judgement: a `credential_phishing` message that an analyst released, and that still
   sits in a VIP inbox, outranks a `malicious` message that is already quarantined.
   `plan.md` section 8 trap 4 of the predecessor task states the trade-off, and no
   `ORDER BY` reaches it, because the severity field and the reachability field point
   in opposite directions.

2. **Incident response.** `docs/vision.md` capability 5a asks for a blast-radius report
   **with a remediation recommendation**. A real recommendation sequences the response,
   scopes notification to the recipients and the VIPs actually reached, and states what
   the absent click telemetry makes unknowable. `src/ray/tools/exposure.py` computes a
   single-rule recommendation inside the tool today: siblings were quarantined, so
   recommend quarantine. IR7 forbids a tool that returns a judgement, so that line is a
   standing violation and not a feature.

The delegation evidence also shapes this record. `progress.md` of the predecessor task
reports that Haiku answered a scope question itself instead of calling
`campaign-correlator`, and that delegation worked at all only after the system prompt
gained explicit per-specialist triggers. Risk R9 is High and risk R11 prices the round
trips. A roster of five peers, each one optional, would make the routing worse.

## Decision

**Five specialists, arranged as a workflow with a gate on each step.**

| Tier | Subagent | Question it answers | Tools |
|---|---|---|---|
| Triage | `triage-officer` | Which items do I work first, and which escalate? | `find_messages`, `get_detection`, `watchlist_sweep`, `recall` |
| Investigation | `auth-forensics` | Does the authentication support the claimed sender? | `get_message`, `find_users`, `domain_intel` |
| Investigation | `campaign-correlator` | Which messages are the same attacker activity? | `find_messages`, `domain_intel`, `entity_graph` |
| Investigation | `verdict-reviewer` | What is the independent verdict, and does it diverge? | `get_detection`, `get_message`, `get_message_body`, `recall` |
| Response | `incident-responder` | What is the response, in what order, and what stays unknown? | `blast_radius`, `get_detection`, `find_users`, `recall` |

**The roster is a workflow, not a set of peers.** The system prompt states three rules.

1. A queue-shaped question enters at `triage-officer`. A question about what to look at,
   about a team over a window, or about what the watchlist catches, is queue-shaped.
2. An investigation specialist runs on its own trigger, unchanged from ADR-008.
3. `incident-responder` runs only after a non-safe finding stands, or when the analyst
   asks who else was hit or what to do. It never runs on a safe message.

Two of the five are therefore gated, so at most three compete for a `task` call on a
typical question. That holds the routing cost near the shipped build.

**Three body-text exclusions, not one.** ADR-008 kept `get_message_body` away from
`auth-forensics`. `triage-officer` and `incident-responder` are excluded on the same
ground. A priority order follows from recorded fields, and a response plan follows from
exposure rows. Neither needs attacker-controlled prose, so neither receives it.

**`blast_radius` stops prescribing.** The tool reports the remediation baseline as
facts: the count of quarantined siblings, the messages still reachable in a mailbox,
and the explicit absence of a baseline when no sibling was quarantined.
`incident-responder` turns those facts into a sequenced recommendation. This restores
IR7 for the tool layer.

**Ray still never acts.** `docs/vision.md` section 4.2 item 3 holds without change.
`incident-responder` recommends, and it states in every answer that Ray cannot
quarantine, release, notify, or reset anything.

**The triage queue is a pull, never a feed.** IR9 holds without change. Nothing appends
to this database. `triage-officer` works recorded rows and `watchlist_sweep` matches,
and it must never present a match as newly arriving.

## Alternatives Considered

**Keep three specialists and reframe their prompts in SOC-role language.** Rejected as
the target, though it is the cheapest option and it needs no amendment to any document.
It supplies no triage judgement and no response judgement, so it leaves the
`exposure.py` violation of IR7 in place and answers neither part of the request.

**A subagent for each of the six capability classes.** Rejected, for the reason ADR-008
gave: an indicator lookup and a count are retrieval, so those specialists would forward
tool output and spend a round trip for nothing.

**A nested handoff, with `triage-officer` delegating onward.** `deepagents` supports it
through `CompiledSubAgent`, so a specialist could hold its own `task` tool. Rejected. It
multiplies the round trips that risk R11 already prices, it hides a delegation from the
main agent's trace, and the analyst then cannot see which specialist reached which
finding, which is goal 3. The main agent orchestrates the handoff instead.

**A sixth specialist for user-reported phishing.** Rejected. A real SOC triages user
reports, and this database holds no report table, so the role would have no input.
`conversation.md` defers it.

## Consequences

**Positive.** The roster now covers the three things `docs/vision.md` section 1 says Ray
exists for: what happened, why it happened, and what to do next. The response
recommendation moves from a single rule inside a tool to a promptable specialist, which
removes a standing IR7 violation. Triage gives capability 1 an ordered answer instead of
a list. The gating keeps the delegation cost close to the shipped build.

**Negative.** Five specialists on a small model is a routing risk, and risk R14 records
it. The recommendation now depends on a delegation that the model may skip, where the
shipped build always printed one line; risk R13 records that regression and the
mitigation. The saved transcripts and their specialist badges are invalidated, so stage
8 re-records them.

**Follow-up.** Keep each tool set minimal, and keep the three body-text exclusions.
Measure which specialists a live run actually reaches, and record the result in
`progress.md`, exactly as the predecessor task recorded its delegation failure.
