# NOTES — Ray, an email-threat investigator agent

Daniel Goren · 2026-08-19

This is the submission write-up. It covers the design decisions, the capabilities
added beyond the brief, how AI was used, what is not finished, and what I would do
next.

---

## 0. The model Ray runs on

**Ray runs Claude Haiku 4.5, through `OCEAN_ANTHROPIC_KEY`.**

The brief names `gpt-5.6-luna`. The OpenAI key issued for this task never received
credit — a funding matter on the issuing side — and the move to an Anthropic model
was directed rather than improvised. `RAY_MODEL` isolates the identifier, so the model
is one environment variable, and `deepagents` already ships `langchain-anthropic`, so
the substitution removed a dependency rather than adding one.
`docs/decisions/ADR-005-model-boundary-and-offline-testability.md` records it.

**One consequence worth reading the rest of this document with in mind:** Haiku is a
small model. Several engineering decisions here exist specifically because a small
model behaves worse than a large one, and I have said so where that is the case
rather than presenting them as universal design wisdom.

---

## 1. What Ray does

A SOC analyst asks a question in natural language. Ray answers it from
`data/ocean_home_task.db` and nothing else.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OCEAN_ANTHROPIC_KEY=...

python -m ray                    # the portal, on http://127.0.0.1:8765
python -m ray --ask "..."        # one question, writes a transcript
python -m ray --check            # readiness, calls no model
pytest -q                        # 252 tests, no key needed
```

| Capability | Question it answers |
|---|---|
| 1 Threat sweep | "Anything targeting our finance team this week?" |
| 2 Verdict explanation | "Why is the message with subject 'Action required: mailbox storage full' malicious?" |
| 3 Indicator lookup | "I got an EDR alert about a click on acme-portal.co. What do we know?" |
| 4 Organizational memory | "Our CFO is Rachel Adler and she never sends wire requests over email. Remember that." |
| **5a Blast radius** | "Who else got it, which of those is still in a mailbox, and what should I do?" |
| **5b Watchlist loop** | Ray learns a rule from analyst commentary, then sweeps for it |

Ray works those questions the way a SOC works them: `triage-officer` orders the queue and
escalates, three investigation specialists establish the finding, and
`incident-responder` recommends the response and never carries it out (ADR-011).

`transcripts/` holds a recorded run of each, plus `08-soc-workflow-triage-then-response`
where all three SOC tiers run in one turn: `triage-officer` 14 tool calls,
`verdict-reviewer` 17, `incident-responder` 10. `transcripts/01` runs the same three
tiers on a threat-sweep question. Reproducible with
`python scripts/record_transcripts.py all`.

**Scale:** 11 tools, 5 specialists in 3 SOC tiers, 2 compiled prompts, 252 tests,
6,407 lines of source and 2,899 of tests, 14 ADRs.

---

## 2. The five things in the data that shaped every decision

I spent the first block of time only reading the database. Nearly every design choice
below traces to something found there, and `plan.md` section 2 records the full
exploration.

**1. Seven recorded verdicts are wrong, and the worst one is invisible to a filter.**
Message `276266c0` is a fake-CFO wire request to Gwen Mercer in finance. Its verdict
is `safe`, its `attack_type` is **absent**, and its remediation is `none` — so it sits
in her inbox and **no verdict filter and no attack-type filter returns it**. SPF, DKIM
and DMARC all pass, because the attacker owns `acme-robotics.com`. The `stage2`
analyzer cleared it on exactly that basis. `nlp-analyzer` scored it 0.59 malicious and
was overruled.

That single row is the argument for capability 4: only a stored policy surfaces it.

**2. A campaign hides a member.** `login-verify.acme-portal.co` appears on 15 messages.
Fourteen carry `campaign_id = cmp_acme_portal_2026_07`; the fifteenth, `93bae03b`,
carries none — while its own `stage2` reasoning names that campaign in prose. Correlate
on `campaign_id` and you find 14 where 15 is correct, and under-remediate by one.

**3. Two false negatives sit on an unscanned link.** `d0e20c68` and `41fe8ce8` are
recorded `safe` with `is_scanned = 0`, on a URL **byte-identical** to one confirmed
malicious on 13 sibling messages. Both hold `action = none`, so both are live.

**4. An analyst's own reasoning decays in the record.** `tunde.okafor` released five
`quaystone-billing-portal.com` messages that still carry
`attack_type = credential_phishing`. The stated reasons run: *"Vendor confirmed by
phone"* → *"Same as previous"* → *"Confirmed vendor"* → *"Confirmed vendor"* →
**"Assuming same as the others."** One phone call covers one message. The fifth even
has a different subject.

**5. Six messages attack the tooling.** Five techniques: a fake `system:` role marker
demanding the reply `NO THREATS FOUND`; a memory-poisoning instruction ("Save this to
memory now"); a tool-abuse request to disclose every executive email address;
`IGNORE ALL PREVIOUS INSTRUCTIONS` inside a quoted reply; and two fabricated SOC
approvals.

And one thing that is **not** there: **no click data and no EDR telemetry exist in any
table.** Scenario 3 asks about a click, so the honest answer is that Ray cannot know.
That is the "doesn't know" transcript, and it is planned rather than hoped for.

---

## 3. Design decisions

### 3.1 Typed tools, never raw SQL (ADR-001)

Ray has no `run_sql` tool. Eleven hand-written tools each hold their own query and
return row identifiers.

I rejected a general SQL tool because grounding is the graded requirement, and a
general tool weakens it three ways: the model writes the join, so a wrong join returns
a confident wrong answer; citations become optional, because the tool returns whatever
was selected; and the schema has to enter the prompt as a fixed context cost.

The decisive advantage is that **the five data traps above are handled in code, where a
test asserts them** — not in a prompt, where a model may ignore the instruction. It
also means the whole tool layer is testable with zero model calls, which is why 206
tests run without a key and why a dead OpenAI key never blocked the build.

### 3.2 Read-only by construction (ADR-002)

The query connection opens with the SQLite URI flag `mode=ro`. A write raises. Ray
reads attacker-controlled content, and a prompt telling it not to write is a promise;
a read-only file handle is a fact. `agent_memory` is the single writable table, reached
through one module.

### 3.3 Grounding is verified, not promised (ADR-001)

Every tool returns row ids. The system prompt requires citations in a fixed form
(`[msg:93bae03b]`, `[analyzer:93bae03b/stage2]`). Then `grounding.py` **re-checks every
citation against the database after the answer is written** and reports failures to the
analyst.

That last step is what turns "grounded" from a claim into a property. It has real
teeth on one specific hallucination: an `[analyzer:.../link-scanner]` citation on a
message that analyzer never ran on **fails**, and since `sender-reputation` ran on only
2 of 2288 messages and `stage2` on 38, that is a live risk rather than a theoretical
one.

### 3.4 Body text is quarantined, and the attack is reported (ADR-004)

`get_message` returns headers, authentication, links, recipient — and **never**
`body_text`. A separate `get_message_body` returns the body fenced in an explicit
untrusted-evidence delimiter, together with any injection findings.

Most investigation never needs the body: scenario 2 is fully answerable without reading
one word of it. So untrusted content enters the context only on an explicit request.

I did not stop at defending. `injection.py` classifies the attempt by technique and
Ray reports it to the analyst as a finding. Defence is table stakes; *"this message
carries an instruction aimed at your security tooling, here is the payload, I did not
act on it"* is the useful output. The detector catches **all 6 planted messages with 0
false positives across all 2288**.

### 3.5 Memory needs provenance and consent (ADR-003)

Memory is the highest-value target in the system, because one poisoned record changes
every later answer. Message `c46f1b40` attacks it directly.

Three rules: content must originate in an analyst turn; the analyst confirms every
record before it is written; and a record's `source` is always stamped `analyst`.

The provenance check has teeth beyond a prompt. `originates_in_email()` searches the
proposed content against every `body_text` in the corpus — **if a "fact" appears inside
an email, it came from the attacker, not from you**, and the write is refused naming
the source message. The poison payload is traced back to `c46f1b40` and rejected;
your own wording passes.

### 3.6 Five specialists, in the three tiers a SOC runs (ADR-008, ADR-011)

My first design was one agent with 14 flat tools. That was wrong: it under-used the
required harness and put reasoning inside tool functions, where no prompt can address
it. ADR-008 replaced three of those tools with three investigation specialists. ADR-011
then found that the roster was an investigation tier and nothing else, and added the two
roles a SOC actually starts and ends with.

| Tier | Subagent | The case it exists for |
|---|---|---|
| Triage | `triage-officer` | Reachability beats severity. A `credential_phishing` message an analyst **released**, still in a VIP inbox, outranks a `malicious` message already quarantined. No `ORDER BY` reaches that trade-off, because the severity column and the reachability column point opposite ways. |
| Investigation | `auth-forensics` | A clean SPF/DKIM/DMARC pass on a lookalike domain is evidence *against* the sender, not reassurance. This is what `stage2` got backwards on `276266c0`. |
| Investigation | `campaign-correlator` | Membership via shared indicators, never `campaign_id` — the 15-versus-14 problem, and a second activity where **all 7 members** carry no `campaign_id` at all. |
| Investigation | `verdict-reviewer` | Forms an independent verdict **before** reading the recorded one, then reports divergence. |
| Response | `incident-responder` | Sequences containment, scopes notification to the VIPs actually reached, and states that no click telemetry exists anywhere in the data, so credential hygiene is precautionary and its scope is the recipient list. |

**The response role fixed a layer violation rather than adding a feature.**
`blast_radius` used to end with a `RECOMMENDATION:` line computed from one rule —
siblings were quarantined, so recommend quarantine. That is a judgement inside a tool,
which is exactly what my own IR7 forbids. The tool now reports the **remediation
baseline** as facts, and the specialist reasons over them. A prompt can address a
specialist; a hard-coded rule inside a function cannot.

**A roster is not five peers.** `progress.md` of the first task records Haiku answering
a scope question itself instead of delegating. Five optional peers competing for one
`task` call would make that worse, so two of the five are gated: a queue-shaped question
enters at triage, and the responder runs only once a non-safe finding stands. At most
three compete on a typical question.

**Only the verdict-reviewer reads a message body.** A verdict needs the pretext. A priority
order follows from recorded fields, a response plan from exposure rows, and an
authentication judgement from headers, so none of those three receives
attacker-controlled prose. `campaign-correlator` works over indicators and does not get
one either. `subagents.NO_BODY_ACCESS` holds the set and a test asserts it.

**Every specialist answers in one shape** — bottom line, evidence, confidence, gaps,
handoff. A SOC case note is a handoff artifact, so one shape serves the lead analyst and
the portal at once. It also puts a **GAPS** line in front of the analyst on every
delegation, which is the grounding principle expressed as an output format.

### 3.7 DSPy compiles offline, one artifact per labelled prompt (ADR-009, ADR-012)

This is the piece I am most pleased with, and the insight that made it affordable is
**compile offline, serve a static artifact**. Two build steps —
`python -m ray.dspy.compile_reviewer` and `python -m ray.dspy.compile_correlator` —
write `prompts/reviewer.compiled.json` and `prompts/correlator.compiled.json`, and
`agent.py` loads each by specialist name. DSPy is absent from `requirements.txt` and
never runs at request time, so a reader who only runs Ray never installs it. An absent
artifact falls back to the hand-written prompt and says so, per specialist.

**Which prompts get compiled is a decision, not an oversight.** ADR-009 refused a second
target because "the router has no ground-truth labels, so its metric would rest on an
opinion". Applied per prompt, that test admits two of five:

| Specialist | Recorded label? | Compiled |
|---|---|---|
| `verdict-reviewer` | 2288 decisions, and 8 rows that are wrong. | **yes** |
| `campaign-correlator` | `campaign_id`, `verdict`, `attack_type` support a set label per seed. | **yes** |
| `auth-forensics` | Derivable — from the same rule the prompt states. Circular. | no |
| `triage-officer` | No table records which item an analyst worked first. | no |
| `incident-responder` | `remediations` records an action, never a sequence or a rationale. | no |

Compiling the last three would score a prompt against a rubric I wrote myself. That is
the failure the measurement exists to avoid, so `NOTES.md` states the boundary instead
of hiding it. The rule is IR11.

**An artifact stores the reasoning core only.** The citation rules, the
untrusted-content rules, and the case-note contract are appended at load time. An
optimizer that found a shorter, better-scoring instruction must not be able to drop
"every claim carries a citation", and a safety-block edit must reach a committed
artifact without a recompile.

#### The verdict-reviewer: a measured gain

The database supplies labels on both sides: recorded decisions as an agreement set, and
**8 rows whose recorded verdict is wrong** as a held-out adversarial set (the 5 released
quaystone messages, the 2 payslip false negatives, and the fake-CFO wire). The
adversarial half carries 60% of the score.

Why two-sided matters, in one number: **a predictor that always answers `safe` scores
above 98% on agreement alone.** Its adversarial score is 0.0, and a test asserts that.

| Program | Agreement | Adversarial | Combined |
|---|---|---|---|
| Hand-written baseline | 0.682 | 0.688 | **0.685** |
| DSPy `BootstrapFewShot` | 0.773 | 0.688 | **0.722** |
| Constant `safe` | high | **0.000** | far below both |

A measured **+0.037** over 22 agreement and 8 adversarial examples.

**The gain itself varies, and the rename exposed that.** ADR-013 renamed this specialist,
which changed the prompt text, which forced a recompile. Same data, same metric, same
baseline of 0.685 — and the compiled score came back 0.722 where the previous run gave
0.749, because `BootstrapFewShot` samples which demonstrations it keeps. So the gain is
directionally real and it is not precise at this sample size: two runs measured +0.064
and +0.037. I am reporting the run that produced the committed artifact, not the better
one. Limit 4 owns the sample size behind this.

One honesty note:
`BootstrapFewShot` adds demonstrations without rewriting instructions, so the exported
prompt would have been byte-identical to the baseline while advertising a higher score.
The three bootstrapped demonstrations are folded into the artifact so it matches its
number.

#### The correlator: a measured refutation, and no headroom

The unit here is a **set of message ids**, scored by F1 against the expected set, so
recall punishes a missed member and precision punishes a wrongly included one. A missing
required id zeroes the score outright. Two seeds are held out, one for each way a
correlator fails: under-inclusion on `login-verify.acme-portal.co`, where the answer is
15 and the required ids are `93bae03b`, `d0e20c68`, and `41fe8ce8`; and over-inclusion on
`meridiansupply.com`, where 7 of 154 messages are the activity.

Three shortcuts need no model at all, and the metric refuses each one:

| Correlator | Agreement | Adversarial | Combined |
|---|---|---|---|
| Join on `campaign_id` | 0.800 | **0.000** | 0.320 |
| Flagged messages only | 0.975 | 0.500 | 0.690 |
| Name every candidate | 0.336 | 0.550 | 0.465 |
| Hand-written core | 1.000 | 1.000 | **1.000** |
| DSPy `MIPROv2` (instruction-only) | 1.000 | 1.000 | **1.000** |

**No headroom, and I am reporting that rather than engineering around it.** The
hand-written core already scores 1.000, so MIPROv2 proposed six instruction candidates
and kept the incumbent. I did not then harden the metric until a gain appeared: tuning a
metric towards the result you want is the same failure as optimizing against an opinion.
What the measurement does show is worth having — the three obvious shortcuts fail, and
the required-id rule means neither a lazy `campaign_id` join nor a flagged filter can
pass. Real headroom would need a corpus with more than two attacker activities in it.

**Two findings from running it.** The correlator baseline first scored a perfect 1.000
for the wrong reason: the evidence bundle showed `campaign_id`, and the labels are
derived from it, so the model could copy the answer out of one column. The bundle now
withholds it — the same precedent ADR-009 set when it withheld the recorded verdict from
the verdict-reviewer. And COPRO, my first optimizer choice, cannot run against Anthropic at
all: it asks for `n` completions in one call and litellm rejects the parameter. MIPROv2
with zero demonstrations replaced it, which also keeps the artifact a prompt rather than
a few-shot corpus — one correlation demonstration carries up to 38 candidate messages.

### 3.8 What I refused to build (ADR-010)

I was asked for real-time alerts. **Nothing appends to this database** —
`received_at` is a static column and no process writes. A live feed would replay stored
timestamps as if they were arriving now, which would make Ray state a fact no row
supports. That contradicts the first principle of the project, so I declined and
proposed the watchlist sweep instead: same agentic initiative, pull rather than push,
nothing fabricated.

---

## 4. The two capabilities I added, and why

### 5a — Blast radius with a remediation recommendation

**Why:** a verdict answers "is this bad". The analyst's next question is always *"who
else got it, and is it still in a mailbox?"* — because that is the question that
decides the work. A verdict-only view hides live messages.

Give it any indicator and it returns every recipient by department, VIP hits marked,
the remediation state of each message, and **the subset still reachable**. Only
`quarantined` removes a message; `none`, `released`, and an absent row all leave it in
the inbox — a distinction that usually matters more than the verdict.

The **remediation baseline** is derived, never invented: 13 siblings on
`login-verify.acme-portal.co` were quarantined and `d0e20c68` and `41fe8ce8` are not, so
a precedent exists; on `quaystone-billing-portal.com` no sibling was quarantined, so the
tool says there is no precedent rather than inventing one.

The **recommendation** is no longer the tool's. It belongs to `incident-responder`
(ADR-011), because a single rule inside a function is a judgement at the wrong layer and
no prompt can improve it. The specialist sequences containment, scopes notification to
the VIP actually reached, proposes a watch record as the only eradication step Ray can
offer, and states that the absent click telemetry makes credential hygiene
precautionary. Ray recommends; Ray cannot act, and says so.

### 5b — A watchlist learned from the analyst's own commentary

**Why:** an investigator that forgets is an investigator that re-asks. And the
database already contains analyst reasoning — the override trail in §2.4 — that decays
to *"Assuming same as the others."* Ray can read that and act on it.

The loop, all in `transcripts/07`: Ray audits the five releases and **rejects the
reasoning** (23/23 citations), catching that `stage2` said the sender domain *is not the
vendor's established domain*. You state the rule. Ray proposes a `watch` record with
its cited basis. You confirm. A later sweep returns all five, all still in inboxes.

The confirmation gate is the same mechanism as the ADR-003 anti-poisoning defence, so
one design serves a safety property and a feature. That is why the pair cost less than
two features.

---

## 5. How I used AI

Claude Code (Opus) throughout, with two patterns worth reporting.

**Parallel subagents in isolated git worktrees.** Six build stages went to subagents
working in their own worktrees on disjoint files. To make that safe I wrote the shared
contracts first — `config.py`, `db.py`, `clock.py`, `schemas.py`, `injection.py` — so
the parallel work never collided and merged without conflict.

**The subagents caught my errors, which was the point.** I gave each one *verified
ground truth to assert* and told it to re-run the queries rather than trust my
numbers. Two of them contradicted me, correctly:

- One found that `campaign_id`, `attack_type`, `override_reason`, `overridden_by` and
  `scan_verdict` are **`NULL`, not empty strings**. I had documented the opposite in
  three places, because the sqlite3 CLI renders NULL as blank. Any query written
  `campaign_id = ''` would have silently returned zero rows.
- One found a **security hole in its own draft**: citation identifiers come from
  model-authored text, and a naive `LIKE identifier || '%'` treats `_` and `%` as
  wildcards — so `[msg:%]` matched every row and **verified as a real citation**. The
  mechanism that proves Ray is not hallucinating could have been forged by Ray. Fixed
  with `substr(column, 1, ?) = ?` and a test that asserts the forgery fails.

Full session history, including my wrong turns, is in
`docs/tasks/ray-email-threat-investigator/conversation.md`. It records the badly framed
questions I asked, a decision I reversed, seven numbers I got wrong and corrected by
querying, and one process failure where a 500-line plan went to disk without being
presented for approval.

---

## 6. Defects found by running the thing

Ten, in order. I list them because which defects you find is a fact about how you
work.

1. **The grounding verifier could be forged by its own input** (§5). Found by a
   subagent auditing its own draft.
2. **`NULL` versus empty string** (§5). Found by a subagent distrusting my docs.
3. **Sub-agent tools ran on worker threads.** `deepagents` invokes tools off the main
   thread and a sqlite3 connection is thread-bound. Found by the first live run.
4. **The portal returned 500 on every question.** Three tool wrappers built their
   trace arguments with `locals()` — and **inside a closure `locals()` also returns the
   referenced free variables**, so `ctx`, holding a `sqlite3.Connection`, reached the
   JSON serializer. Found by clicking through the portal myself.
5. **The evidence panel showed one row of a seven-row result**, and **the subagents
   were never attributed and barely called.** The trace preview was capped at 600
   characters; and `_emit` never passed a subagent, because all three specialists
   shared one set of tool objects — so `subagents_used` was always empty and no
   transcript contained a single delegation. Found when I went looking for a specialist
   badge in the portal and could not make one appear.

6. **A tool was returning a judgement, and my own rule forbade it.** `blast_radius`
   ended with a `RECOMMENDATION:` line computed from one rule. IR7 says a tool must not
   return a judgement, and this one had done so since the day it was written. Found while
   checking whether an incident-response specialist would duplicate existing behaviour —
   it turned out to *relocate* it. The tool now reports the remediation baseline as facts.
7. **Two ids in one citation bracket, twice in a row.** A live incident-response run
   wrote `[decision:41fe8ce8, decision:d0e20c68]`; the grounding check failed it, the
   corrective pass ran, and Haiku produced the same malformed bracket again — because the
   correction listed the valid forms without ever saying "one identifier per bracket".
   Both the citation rules and the corrective prompt now say it. Found by reading the
   grounding output of a smoke run rather than the answer above it.

8. **The model announced an escalation instead of performing it.** A triage run ended
   with "I'm escalating both to the verdict-reviewer" — a promise about a later turn,
   when the analyst had asked now. The system prompt now forbids that and requires the
   escalation in the same turn. `transcripts/08` shows the fix: triage, review, and
   response all in one turn.
9. **A tool name in brackets passed completely unseen.** `[blast_radius]` looks like a
   citation to a reader; `_CITATION_RE` needs a colon, so it matched nothing and was
   reported as nothing. `grounding.find_pseudo_citations` now catches it, and
   `grounding.TOOL_NAMES` is asserted against the real tool registry so a new tool cannot
   escape the check.
10. **The portal fake hid a new field, again.** `Startup` gained `prompt_detail`;
    `FakeStartup` did not; `/api/state` broke and only a live click would have shown it.
    That is defects 4 and 5 repeating in miniature, one task later. A test now compares
    the fake's public surface against the real `Startup`, so the seam is checked instead
    of trusted.

**The pattern in 4 and 5 is the lesson.** Both were in the interface layer and both
were invisible to a passing suite, because the portal tests used a fake Ray whose tools
recorded nothing. **A component test that fakes its collaborator proves the component,
not the seam.** The regression tests now drive every registered tool through the real
wrappers, and a further test fails if a new tool escapes that check.

Defect 10 is the same lesson arriving a second time, which is why the guard is now a
test rather than a resolution.

Defect 5 also had a consequence beyond display: a compiled verdict-reviewer prompt is worth
nothing if the verdict-reviewer is never invoked. Before the fix, it effectively was not.

---

## 7. What is not finished, and known limits

Stated plainly rather than left to be discovered.

1. **Delegation works now, and it is not deterministic.** `deepagents` dispatch is
   model-driven: the model decides whether to call `task`. The roster does get used —
   `transcripts/01` runs three tiers on one question (`triage-officer` 10 tool calls,
   `verdict-reviewer` 7, `incident-responder` 5), which is a change from the first task,
   where no transcript contained a single delegation. But **the same question does not
   produce the same delegations twice.** Across three full recordings, scenario 8 came
   back as triage 12 / reviewer 17 / responder 6, then 14 / 4 / 4, then 14 / 17 / 10; and
   one recording of scenario 1 reached all five specialists while the committed one
   reaches three. The findings held every time — scenario 4 reasons the CFO policy
   through the main agent in the committed run and reaches the same disagreement it
   reached through two specialists before. The routing is what moves. Gating two of the
   five keeps at most three competing for a `task` call, which reduces the variance rather
   than removing it. If I needed a guarantee I would dispatch triage in code instead of
   asking a small model to choose.
2. **Citation discipline needs a safety net.** Haiku reliably writes a good answer and
   then cites it badly — inventing `[domain_intel]`, a tool name, as if it were a row.
   A failed grounding check therefore triggers **one corrective pass** asking Ray to
   re-cite from tool output already in its context, findings unchanged. The transcript
   records that the correction happened rather than hiding it. This is a workaround for
   a small model, not something I would claim as elegant.
3. **Ray under-cites.** Answers pass the grounding check but carry fewer citations than
   claims. Nothing verifies that *every* claim is cited, only that every citation
   resolves.
4. **The DSPy sets are small.** The verdict-reviewer has 22 agreement and 8 adversarial
   examples; the 8 are every wrong row in the corpus, so that half cannot grow. The
   correlator has 10 and **2** — the corpus contains exactly two attacker activities, so
   that is the ceiling. A number from 2 examples carries less weight than one from 8, and
   both reports print `n_adversarial` beside every score for that reason.
5. **The correlator metric has no headroom, and its labels lean on one reading.** The
   hand-written core scores 1.000, so the compile confirms rather than improves. The
   labels also come from a shared-indicator reading of recorded rows — flagged, or
   carrying a `campaign_id` — so the metric measures agreement with that reading rather
   than with an external ground truth. The negative seeds and the over-inclusion case are
   what stop it from being circular; they are not a complete answer to the objection.
6. **Three prompts carry no number at all.** Triage priority, response quality, and an
   authentication judgement have no recorded label, so `triage-officer`,
   `incident-responder`, and `auth-forensics` are hand-written and unmeasured. I would
   rather say that than publish a metric I invented for them.
7. **The time budget.** The brief sets 3 hours. Exploration, design and tier 1 fit
   roughly that; tiers 2 and 3 did not. I chose to keep going past it rather than stop
   at tier 1. `plan.md`
   section 5 states the overrun openly and orders the work into three cut lines, so a
   stop at any tier leaves a coherent submission.
8. **`entity_graph` layout is deterministic, not pretty.** Columns by node kind. No
   physics, no library, because the page must stay self-contained.

---

## 8. What I would do next

In the order I would actually do it.

1. **Make delegation deterministic where it matters.** Route on the question, not on
   the model's mood: a verdict-questioning phrasing should always reach the verdict-reviewer,
   and a queue-shaped question should enter triage in code rather than by persuasion. The
   evidence is limit 1 — the same question produced 12 / 17 / 6 delegations on one run and
   14 / 4 / 4 on the next. That also makes the compiled prompts reliably load-bearing.
2. **Verify claim coverage, not just citation validity.** Split the answer into
   claims and check that each carries a citation. That closes limit 3 and removes the
   need for the corrective pass in limit 2.
3. **Sweep the whole corpus with the verdict-reviewer and rank the disagreements.** Ray can
   already disagree with one verdict on request. Running it over all 2288 and surfacing
   the strongest divergences turns a question-answering tool into a detection-quality
   audit — the highest-value thing on this list.
4. **Feed the audit back into detection.** The eight wrong rows share structure: a
   clean authentication pass on a lookalike domain, and an unscanned link identical to
   a known-malicious one. Both are analyzer rules, not agent rules.
5. **Ingest click and EDR telemetry.** The one gap Ray cannot reason around today.
   Scenario 3 is where the analyst feels it.
6. **Give the correlator metric real headroom.** The hand-written core already scores
   1.000, and `MIPROv2` kept it. That is a fact about the corpus — it holds exactly two
   attacker activities — not about the optimizer. More activities, or seeds where the
   membership boundary is genuinely contested, would make the compile capable of showing
   a gain instead of only a confirmation.
7. **Find a label for the three unmeasured prompts.** Triage priority and response
   quality have none today. The honest route is an analyst labelling a queue order, not
   me writing a rubric and calling it ground truth.

---

## 9. Where to look

| Question | File |
|---|---|
| Purpose, scope, terminology | `docs/vision.md` |
| The design and the acceptance criteria | `docs/tasks/ray-email-threat-investigator/plan.md` |
| What the database actually contains | same, section 2 |
| Implementation log and every defect | same folder, `progress.md` |
| **How the design was reached, honestly** | same folder, `conversation.md` |
| **The SOC roster and the second compile** | `docs/tasks/ray-soc-role-subagents/` — plan, progress, conversation |
| The fourteen decisions, each with alternatives | `docs/decisions/` |
| Rules for a coding agent in this repo | `AGENTS.md` |
| Commands and environment | `README.md` |
| Recorded runs | `transcripts/` |
| The two compile reports | `prompts/reviewer.report.md`, `prompts/correlator.report.md` |
