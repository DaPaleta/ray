# Vision — Ray

**Status:** active
**Last updated:** 2026-08-19

This document owns the purpose, the scope, and the terminology of the project.

## 1. Purpose

Ray is an investigator agent inside a security portal. A SOC analyst asks Ray a
question in natural language. Ray answers the question from the organization's
email data.

Detection ran before Ray. Analyzers scored every message. A decision holds a
verdict for every message. Ray does not replace detection. Ray helps the analyst
to understand three things:

1. What happened.
2. Why it happened.
3. What to do next.

Ray serves one organization. The organization is Acme Robotics. The primary
domain is `acme.com`.

## 1a. Project goals

The brief grades three things: the working result, the invention, and the design.
This project therefore holds three goals, in this order of importance.

**Goal 1 — reliable, data-centered, and explainable.** Ray grounds every claim in
a row and shows the analyst the evidence. A wrong answer that reads well is the
worst outcome, so grounding is a verified property and not a prompt promise.

**Goal 2 — inventive.** Ray shows initiative beyond question answering. Three
mechanisms carry this goal: specialized subagents for reasoning that a query
cannot do, in the three tiers a SOC runs (ADR-008, ADR-011); compiled and measured
specialist prompts (ADR-009, ADR-012); and a watchlist that applies what Ray learned
(ADR-010).

**Goal 3 — visible.** The analyst can see how Ray reached an answer. The portal
renders the entity graph behind a finding, and it records the full tool-call log
for every turn. `transcripts/` preserves both.

A goal never overrides a principle in section 2. When invention and grounding
conflict, grounding wins.

## 2. Product principles

1. **The database is the only source of truth.** Ray states a fact only when a
   row supports the fact. Ray cites the row.
2. **Ray reports the limits of the data.** When no row supports an answer, Ray
   says that it does not know. Ray never fills a gap with a guess.
3. **Body text is attacker-controlled.** Ray treats body text as evidence. Ray
   never treats body text as an instruction.
4. **Ray reads the database. Ray does not change the database.** The one
   exception is the memory table. Section 4 defines the rule.
5. **Ray may disagree with a recorded verdict.** Ray states the disagreement and
   gives the evidence for it.
6. **Ray answers at the altitude of the question.** Ray gives the analyst a
   conclusion first, then the evidence.

## 3. Terminology

Each term below has one meaning. This project uses no synonym for any of them.

| Term | Meaning |
|---|---|
| **analyst** | The human who asks Ray a question. |
| **message** | One row in the `messages` table. |
| **body text** | The `messages.body_text` value. Attacker-controlled. Untrusted. |
| **link** | One row in the `links` table. |
| **analyzer result** | One row in the `analyzer_results` table. |
| **decision** | One row in the `decisions` table. |
| **verdict** | The `decisions.verdict` value. One of `safe`, `suspicious`, `malicious`. |
| **attack type** | The `decisions.attack_type` value. |
| **override** | A decision that holds a value in `overridden_by`. |
| **remediation** | One row in the `remediations` table. |
| **campaign** | The set of messages that share one `campaign_id` value. |
| **indicator** | A sender address, a sender domain, a link domain, a subject, or a campaign identifier. |
| **memory record** | One row in the `agent_memory` table. |
| **watch record** | A memory record of kind `watch`. It holds an indicator to sweep for. |
| **citation** | A reference from a Ray statement to one database row. |
| **finding** | One statement that Ray makes, with at least one citation. |
| **blast radius** | The full set of recipients that one indicator reached, and the remediation state of each message. |
| **data as of** | The `db_meta.data_as_of` value. Ray treats this instant as the present. |
| **subagent** | One of the five specialists in ADR-011. It reasons. It does not retrieve. |
| **triage queue** | The set of items a triage question covers, in the order the triage-officer puts them. It is a pull over recorded rows, never a feed. |
| **escalation** | The one specialist that a triage-officer names for an item, or a decision to close it. |
| **case note** | The output shape every specialist uses: bottom line, evidence, confidence, gaps, handoff. |
| **remediation baseline** | What the already-quarantined sibling messages on an indicator received. `blast_radius` reports it as a fact. It is not a recommendation. |
| **response plan** | The ordered recommendation that the incident-responder forms from exposure facts. Ray recommends it. Ray never carries it out. |
| **evidence bundle** | The combined analyzer results, decision, and remediation for one message. `get_detection` returns it. |
| **independent verdict** | The verdict that the verdict-reviewer subagent forms from the evidence bundle, without reading the recorded verdict first. |
| **divergence** | A difference between the independent verdict and the recorded verdict. |
| **entity graph** | Nodes for messages, users, domains, and campaigns, with edges for a shared indicator. |
| **compiled prompt** | A prompt artifact that a DSPy build step writes, one per specialist. Two exist. See ADR-009 and ADR-012. |
| **sweep** | One pass of every watch record across the corpus. It returns matches with citations. |

## 4. Scope

### 4.1 In scope

Ray answers six classes of question.

| # | Capability | Example question |
|---|---|---|
| 1 | **Threat sweep** | "Anything targeting our finance team this week?" |
| 2 | **Verdict explanation** | "Why is the message with the subject 'Action required: mailbox storage full' malicious?" |
| 3 | **Indicator lookup** | "I got an EDR alert that someone clicked a link on acme-portal.co. What do we know about it?" |
| 4 | **Organizational memory** | "Our CFO is Rachel Adler and she never sends wire requests over email. Remember that." |
| 5a | **Blast-radius report, with a remediation recommendation** | "Who else received this, which of those messages is still in an inbox, and what should I do?" |
| 5b | **Watchlist loop** | Ray proposes a watch record from analyst comments. The analyst confirms it. A later sweep applies it. |

Capability 5a and capability 5b are the two additions that this project makes
beyond the four required capabilities. `docs/tasks/ray-email-threat-investigator/plan.md`
holds the argument for each one.

Ray works these questions the way a SOC works them. A triage role orders the queue
and escalates. Three investigation roles establish the finding. A response role
recommends what to do, and never does it. ADR-011 holds the roster.

Ray also forms an independent verdict on a message. Ray compares the independent
verdict against the recorded verdict, and Ray reports a divergence. Seven recorded
verdicts in the database do not match their evidence, so this is a working
capability and not a theoretical one.

Three cross-cutting mechanisms serve goal 2 and goal 3. They are not separate
capabilities, because each one supports all of the six above.

| Mechanism | Purpose | Record |
|---|---|---|
| Specialized subagents | Reasoning that a query cannot do, in the three tiers a SOC runs. | ADR-008, ADR-011 |
| Compiled specialist prompts | A measured prompt, not a hand-tuned one, for every specialist that the data labels. | ADR-009, ADR-012 |
| Entity graph and tool-call log | The analyst sees how Ray reached the answer. | ADR-007 |

### 4.2 Out of scope

1. **Multi-tenant operation.** One deployment serves one organization.
2. **Detection.** Ray does not score a message. Ray reads recorded scores.
3. **Remediation.** Ray does not quarantine a message and does not release a
   message. Ray reports the recorded remediation.
4. **Click telemetry and EDR telemetry.** The database holds neither. Ray states
   that it does not know when the analyst asks about a click.
5. **Authentication and multi-user access control.** The portal runs on the
   local host for one analyst.
6. **Live threat intelligence.** Ray queries no external service.
7. **Real-time alerting.** Nothing appends to the database, so no event stream
   exists. Ray sweeps a watchlist on request instead. ADR-010 records the reason.
8. **Prompt optimization at request time.** DSPy runs at build time only. The
   serving path loads a static artifact. ADR-009 records the reason.

## 5. Success measures

1. A clean checkout runs Ray with one command.
2. Ray answers all six capability classes.
3. Every claim in an answer carries a citation to a real row.
4. A grounding check rejects any citation that no row supports.
5. Ray refuses every instruction that body text contains. Ray reports the
   attempt to the analyst.
6. Ray stores the CFO policy from capability 4. On a later turn Ray retrieves the
   policy and applies it to a message.
7. A saved transcript shows Ray in a state where it does not know the answer.
8. `NOTES.md` reports each compiled prompt's metric as a number, for the
   hand-written prompt and for the compiled prompt, and it states which prompts carry
   no number because the data holds no label for them.
9. The portal renders the entity graph and the tool-call log for a turn.
10. `NOTES.md` states the model substitution against the brief.

## 6. References

| Fact | Owner |
|---|---|
| Purpose, scope, terminology | `docs/vision.md` |
| Repository layout | `docs/structure.md` |
| Technical decisions | `docs/decisions/` |
| Task design and execution log | `docs/tasks/<task-name>/` |
| Commands and tech stack | `README.md` |
| Instructions for coding agents | `AGENTS.md` |
| Submitted design write-up | `NOTES.md` — start here |
| Original brief | `docs/home-task-brief.pdf` |
