# Plan — SOC role subagents, and a compiled prompt for every labelled specialist

**Status:** implemented. See `progress.md` stage 8 for the verification.
**Created:** 2026-08-19
**Owner:** Daniel Goren
**Jira ticket:** none. This task continues the external home assignment, not Evinced work.

This document uses Simplified Technical English. `docs/vision.md` section 3 owns the
terminology. The predecessor task is `docs/tasks/ray-email-threat-investigator/`, and
its section 8 implementation rules IR1 to IR10 still bind this work.

## 1. Context

The analyst asked for two improvements.

1. **Make the specialists work the way a real SOC works.** Add a triage role that
   works the queue and escalates. Add an incident-response role that recommends the
   response. Reframe the three existing specialists as the investigation tier.
2. **Write the specialist prompts with DSPy.** The predecessor task compiles one
   prompt. Compile every prompt for which the database yields a real label.

### 1.1 What already fits the vision

| Request | Where it already fits |
|---|---|
| A specialist recommends a response. | `docs/vision.md` section 1 — Ray answers "what to do next". Capability 5a is a blast-radius report **with a remediation recommendation**. |
| A specialist triages data and prioritizes. | `plan.md` section 8 traps 1 and 4 of the predecessor task. Ranking a released `credential_phishing` message in a VIP inbox above a quarantined `malicious` message is a judgement. No `ORDER BY` reaches it. |
| DSPy writes more prompts. | `docs/vision.md` section 4.2 item 8 excludes prompt optimization **at request time** only. A build-time compile of a second prompt adds no request-time dependency. |

### 1.2 What did not fit, and what this task amends

| Blocking statement | Amendment |
|---|---|
| ADR-008: "Three, and no more. A fourth subagent would need a fourth such task." | ADR-011 states the reasoning task that each new role earns its place with, and amends the roster to five. |
| `docs/vision.md` section 3: "**subagent** — One of the three specialists in ADR-008." | Section 3 now reads "One of the five specialists in ADR-011", and the section gains four terms. |
| `docs/structure.md` section 3a lists three subagents. | The table lists five. It also repairs pre-existing drift: `verdict-reviewer` reaches `get_message`, which the table omitted. |
| IR7: "Three subagents reason." | ADR-011 amends the count. The rule itself is unchanged and now binds five specialists. |
| ADR-009 compiles one prompt, and rejected a second target for want of labels. | ADR-012 keeps that test and applies it per prompt. Two prompts have labels. Three do not, and they stay hand-written. |

### 1.3 What stays out of scope

1. **A live alert feed.** IR9 and `docs/vision.md` section 4.2 item 7 hold. Nothing
   appends to this database. The triage queue is a pull over recorded rows and over
   `watchlist_sweep` matches. `triage-officer` must never present a match as newly
   arriving.
2. **Remediation.** `docs/vision.md` section 4.2 item 3 holds. `incident-responder`
   recommends a response. It never quarantines, releases, notifies, or resets
   anything, and it says so in every answer.
3. **A compiled triage prompt or a compiled response prompt.** No label exists for
   either. Section 4.3 holds the argument.

## 2. The roster

Five specialists, in the three tiers a SOC actually runs.

| Tier | Subagent | Question it answers | Reasoning a query cannot do |
|---|---|---|---|
| Triage | `triage-officer` | Which of these items do I work first, and which escalate? | A released `credential_phishing` message still in a VIP inbox outranks a quarantined `malicious` message. Severity, reachability, and who was hit trade off against each other. |
| Investigation | `auth-forensics` | Does the authentication result support the claimed sender? | A clean SPF, DKIM, and DMARC pass on a lookalike domain is evidence **against** the sender. |
| Investigation | `campaign-correlator` | Which messages belong to the same attacker activity? | Membership by shared indicator, never by `campaign_id`. Two activities in this data prove the point. Section 3 holds them. |
| Investigation | `verdict-reviewer` | What is the independent verdict, and does it diverge from the record? | Eight recorded verdicts do not match their evidence. |
| Response | `incident-responder` | Given a confirmed finding, what is the response, in what order, and what remains unknown? | Sequencing containment, scoping notification to the recipients and the VIPs actually reached, and stating what the absent click telemetry makes unknowable. |

### 2.1 Tool sets

Each specialist reaches the minimum tool set for its question. IR7 holds.

| Subagent | Tools |
|---|---|
| `triage-officer` | `find_messages`, `get_detection`, `watchlist_sweep`, `recall` |
| `auth-forensics` | `get_message`, `find_users`, `domain_intel` |
| `campaign-correlator` | `find_messages`, `domain_intel`, `entity_graph` |
| `verdict-reviewer` | `get_detection`, `get_message`, `get_message_body`, `recall` |
| `incident-responder` | `blast_radius`, `get_detection`, `find_users`, `recall` |

`auth-forensics` still receives no `get_message_body`. `triage-officer` receives none
either: a triage decision reads recorded fields, and untrusted content has no place
in a prioritization context. `incident-responder` receives none: a response plan
follows from exposure rows, not from what the attacker wrote.

### 2.2 Routing, and why it is a workflow and not five peers

`progress.md` of the predecessor task records the delegation problem: Haiku answered
a scope question itself instead of calling `campaign-correlator`, and delegation
worked at all only after the system prompt gained explicit triggers. Five peers
competing for one `task` call would make that worse, and risk R11 prices the round
trips.

The system prompt therefore states a workflow with a gate on each step.

1. A queue-shaped question enters at `triage-officer`. "What should I look at",
   "anything targeting finance this week", and "what does the watchlist catch" are
   queue-shaped.
2. An investigation specialist runs on its own trigger, unchanged from the
   predecessor task.
3. `incident-responder` runs **only** after a non-safe finding stands, either
   recorded or reached by `verdict-reviewer`, or when the analyst asks who else
   was hit or what to do. It never runs on a safe message.

## 3. The two attacker activities in this data

Both matter, because ADR-012 builds the correlator labels from them. Every number
below comes from a query run against `data/ocean_home_task.db`.

| Activity | Messages | `campaign_id` | Shared indicator |
|---|---|---|---|
| acme-portal | 15 | 14 carry `cmp_acme_portal_2026_07`. `93bae03b` carries none. | Link domain `login-verify.acme-portal.co`. Three pretexts: open enrolment (5), payslip (5), unusual sign-in (4). |
| meridiansupply | 7 | **None of the 7 carries one.** | Link domain `portal.meridiansupply.com`, sender `statements@meridiansupply.com`, subject "Statement of account". |

The meridiansupply activity is the harder case, and this task found it. The sender
domain `meridiansupply.com` sends 154 messages, and 147 of them are legitimate. A
correlator that answers "the whole domain" is wrong by a factor of 22. A correlator
that answers "the recorded campaign" returns nothing at all, because the recorded
`campaign_id` is empty on all 7.

## 4. Approach

### 4.1 The layer repair that `incident-responder` performs

`src/ray/tools/exposure.py` lines 275 to 297 emit a `RECOMMENDATION:` block. The tool
computes it from one rule: siblings on this indicator were quarantined, so recommend
quarantine. That is a judgement inside a tool, and IR7 forbids it.

`blast_radius` now reports the **remediation baseline** as facts: how many sibling
messages were quarantined, which messages remain reachable in a mailbox, and that no
baseline exists when no sibling was quarantined. `incident-responder` turns those
facts into a sequenced recommendation.

**Accepted regression risk.** When the model does not delegate, the analyst sees the
exposure facts and no prescription, where the shipped build always printed one line.
Risk R13 records it. The mitigation is the gate in section 2.2 plus a statement in
the system prompt: after `blast_radius` on a non-safe indicator, delegate.

### 4.2 One compiled artifact for each labelled prompt

`prompts/` gains one artifact per compiled specialist, named for the specialist.

| Artifact | Specialist | Label source |
|---|---|---|
| `prompts/reviewer.compiled.json` | `verdict-reviewer` | 2288 recorded decisions, and the 8 rows whose recorded verdict is wrong. ADR-009. |
| `prompts/correlator.compiled.json` | `campaign-correlator` | Recorded `campaign_id`, the two activities in section 3, and the benign sender clusters. ADR-012. |

`config.py` resolves an artifact by specialist name under a prompts directory.
`subagents.py` loads a prompt per specialist, and falls back per specialist. An absent
artifact stays a supported state, never a crash. IR8 holds.

### 4.3 The correlator metric, and why it cannot be gamed

The metric mirrors ADR-009: an agreement half, an adversarial half held out of
bootstrapping, and the adversarial half weighted at 60 percent.

The unit of comparison is a **set of message identifiers**. The score is the F1 of the
predicted set against the expected set, so an over-inclusive answer loses precision
and an under-inclusive answer loses recall.

**Agreement examples.** Seed an indicator, and expect the set that the recorded rows
support. Positive seeds come from the two activities: the sender domain, and each
subject pretext. Negative seeds come from the benign sender clusters, such as
`tessellate.dev` with 166 messages and no non-safe verdict; there the expected set is
empty, because a shared sender domain with no flagged message is not an attacker
activity.

**Adversarial examples.** Two, one for each way a correlator fails.

1. **Under-inclusion.** Seed `login-verify.acme-portal.co`. The expected set holds 15
   members, including `93bae03b`, whose `campaign_id` is empty. The score is the F1
   multiplied by zero unless `93bae03b` appears. A `campaign_id` join scores **0.0**.
2. **Over-inclusion.** Seed `meridiansupply.com`. The expected set holds the 7 flagged
   messages only. An answer of "every message from this domain" scores an F1 of about
   0.09.

`correlation.py` ships a `campaign_id_baseline` function, the analogue of ADR-009's
`constant_safe_baseline`. It demonstrates the 0.0 on the adversarial half, and a test
asserts it with no model call.

### 4.4 What stays hand-written, and why

`triage-officer` and `incident-responder` receive no compiled prompt. A priority order
and a response plan have no recorded label in this database. A metric for either one
would score the prompt against an opinion that this task wrote, which is the exact
argument ADR-009 used to reject compiling the router. `NOTES.md` states this, so the
reader sees the boundary of the measured claim.

## 5. Work breakdown

| # | Stage | Output |
|---|---|---|
| 1 | Docs and decisions | This plan, ADR-011, ADR-012, and the amendments in section 1.2. |
| 2 | Prompts | Five specialist prompts in SOC-role language. A workflow routing section in the system prompt. |
| 3 | Roster | `subagents.py` with five specialists and per-specialist compiled prompt loading. `config.py` and `agent.py` follow. |
| 4 | Layer repair | `exposure.py` reports the baseline as facts. Tests follow. |
| 5 | Correlator labels and metric | `dspy/correlation.py`, and tests that need no model. |
| 6 | Correlator compile | `dspy/compile_correlator.py`, `prompts/correlator.compiled.json`, `prompts/correlator.report.md`. |
| 7 | Portal | A badge and a role line for each of the five specialists. |
| 8 | Verification | `pytest`, a live run, re-recorded transcripts, and the write-up. |

## 6. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R13 | The recommendation regresses when the model does not delegate to `incident-responder`. | **High** | The gate in section 2.2, an explicit post-`blast_radius` instruction in the system prompt, and the baseline facts stay in the tool output. A live run verifies the delegation. |
| R14 | Five specialists on a small model make routing less reliable, not more. | **High** | The workflow in section 2.2 gates two of the five, so at most three compete on a typical question. A live run measures which specialists a scenario reaches. |
| R15 | The correlator adversarial half rests on 2 examples, against the verdict-reviewer's 8. | Medium | Report `n_adversarial` beside every score. Never present the correlator number as the stronger measurement. |
| R16 | The correlator labels are derived by the same shared-indicator rule that the prompt states, so the metric measures the rule. | Medium | The labels come from recorded rows: `campaign_id`, `verdict`, and `attack_type`. The negative seeds and the over-inclusion adversarial case cannot be passed by applying the rule alone, because both need a judgement about which shared indicator is strong enough. `NOTES.md` states the limit. |
| R17 | Changing the roster invalidates the saved transcripts and the specialist badges in them. | Medium | Re-record the transcripts in stage 8. The predecessor task already re-recorded four of them, so the procedure exists in `scripts/record_transcripts.py`. |
| R18 | The compile costs model calls, and a failed run leaves a stale artifact. | Low | `compile_correlator.py` follows `compile_reviewer.py`: it writes an honest baseline-only artifact before the optimizer runs, and it names the optimizer in the artifact. |

## 7. Acceptance criteria

1. `pytest` passes.
2. `build_subagents` returns five specialists. Each one holds the tool set in section
   2.1, and no other.
3. `auth-forensics`, `triage-officer`, and `incident-responder` receive no
   `get_message_body`.
4. `blast_radius` emits no prescription. A test asserts that the word
   `RECOMMENDATION` is absent, and that the baseline facts are present.
5. `load_compiled_prompts` returns a prompt for `verdict-reviewer` and for
   `campaign-correlator`, and a status line for each of the five.
6. An absent artifact directory produces five fallback status lines and no exception.
7. `correlation.campaign_id_baseline` scores 0.0 on the adversarial half. A test
   asserts it, and the test calls no model.
8. `prompts/correlator.compiled.json` and `prompts/correlator.report.md` exist, and
   the report holds the baseline score and the compiled score with `n_agreement` and
   `n_adversarial`.
9. The portal renders a badge for each of the five specialists.
10. A live run shows `triage-officer` and `incident-responder` invoked and attributed
    in the trace.
11. `NOTES.md` reports both compile results, and states that two prompts stay
    hand-written because no label exists for them.
12. The drift checklist in `AGENTS.md` is clear, and a secret scan passes.

## 8. Implementation rules

IR1 to IR10 of the predecessor task bind this work unchanged, with two amendments.

**IR7 amended.** Five subagents reason, not three. The rule itself holds: a tool must
never return a verdict, a conclusion, or a judgement. This task removes one violation
of it from `exposure.py`.

**IR8 extended.** The rule now covers every compiled artifact. Nothing in the serving
path imports DSPy. Every artifact loads by specialist name, and every absent artifact
falls back to the hand-written prompt with a reported status.

**IR11 — new. A prompt is compiled only against a recorded label.** A metric that
scores a prompt against an opinion this repository wrote is not a measurement. When
the database holds no label for a specialist's output, the prompt stays hand-written
and `NOTES.md` says so.

## 9. Definition of done

The predecessor task's section 9 holds, unchanged: `pytest` passes, every new query
has a test that asserts a known row, IR1 to IR11 hold, the drift checklist is clear,
every documented number comes from a query, and the repository-wide secret scan
passes.
