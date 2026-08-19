# NOTES — Ray, an email-threat investigator agent

Daniel Goren · 2026-08-19

This is the submission write-up. It covers the design decisions, the capabilities
added beyond the brief, how AI was used, what is not finished, and what I would do
next.

---

## 0. Read this first: one deviation from the brief

**The brief specifies `gpt-5.6-luna`. Ray runs Claude Haiku 4.5.**

The OpenAI key issued to me never received credit, so the model it names was never
reachable. Rather than hold the whole build behind a key I did not control, I moved to
an Anthropic key I did have. `RAY_MODEL` isolates the identifier, so the change is one
environment variable, and `deepagents` already ships `langchain-anthropic`, so the
substitution removed a dependency rather than adding one.

I am flagging this at the top rather than in a footnote. An unannounced swap of a
mandated model is the one version of this that would be dishonest.
`docs/decisions/ADR-005-model-boundary-and-offline-testability.md` records the
decision, and it is tracked as risk R1 in the plan.

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
pytest -q                        # 201 tests, no key needed
```

| Capability | Question it answers |
|---|---|
| 1 Threat sweep | "Anything targeting our finance team this week?" |
| 2 Verdict explanation | "Why is the message with subject 'Action required: mailbox storage full' malicious?" |
| 3 Indicator lookup | "I got an EDR alert about a click on acme-portal.co. What do we know?" |
| 4 Organizational memory | "Our CFO is Rachel Adler and she never sends wire requests over email. Remember that." |
| **5a Blast radius** | "Who else got it, which of those is still in a mailbox, and what should I do?" |
| **5b Watchlist loop** | Ray learns a rule from analyst commentary, then sweeps for it |

`transcripts/` holds a recorded run of each, reproducible with
`python scripts/record_transcripts.py all`.

**Scale:** 11 tools, 3 subagents, 201 tests, ~5,100 lines of source and ~2,400 lines
of tests, 10 ADRs.

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
also means the whole tool layer is testable with zero model calls, which is why 201
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

### 3.6 Three subagents, for reasoning a query cannot do (ADR-008)

My first design was one agent with 14 flat tools. That was wrong: it under-used the
required harness and put reasoning inside tool functions, where no prompt can address
it. Three specialists now own the judgement calls:

| Subagent | The case it exists for |
|---|---|
| `auth-forensics` | A clean SPF/DKIM/DMARC pass on a lookalike domain is evidence *against* the sender, not reassurance. This is what `stage2` got backwards on `276266c0`. |
| `campaign-correlator` | Membership via shared indicators, never `campaign_id` — the 15-versus-14 problem. |
| `verdict-adjudicator` | Forms an independent verdict **before** reading the recorded one, then reports divergence. |

`auth-forensics` deliberately has no access to `get_message_body`: it reasons about
headers, so untrusted content has no business in its context.

### 3.7 DSPy compiles offline into a static artifact (ADR-009)

This is the piece I am most pleased with, and the insight that made it affordable is
**compile offline, serve a static artifact**. `python -m ray.dspy.compile_adjudicator`
runs at build time and writes `prompts/adjudicator.compiled.json`; `agent.py` loads it.
DSPy is absent from `requirements.txt` and never runs at request time, so a reviewer
who only runs Ray never installs it. An absent artifact falls back to the hand-written
prompt and says so.

**The metric is the substance, not the optimizer.** The database supplies labels on
both sides: 2288 recorded decisions as an agreement set, and **8 rows whose recorded
verdict is wrong** as a held-out adversarial set (the 5 released quaystone messages,
the 2 payslip false negatives, and the fake-CFO wire). The adversarial half carries
60% of the score.

Why two-sided matters, in one number: **a predictor that always answers `safe` scores
above 98% on agreement alone.** That is exactly the failure this project exists to
catch, so a one-sided metric would have rewarded it. Its adversarial score is 0.0, and
a test asserts that.

| Program | Agreement | Adversarial | Combined |
|---|---|---|---|
| Hand-written baseline | 0.625 | 0.688 | **0.6625** |
| DSPy `BootstrapFewShot` | 0.833 | 0.688 | **0.7458** |
| Constant `safe` | high | **0.000** | far below both |

A measured **+0.083**, from ~52 Haiku calls. One honesty note: `BootstrapFewShot` adds
demonstrations without rewriting instructions, so the exported prompt would have been
byte-identical to the baseline while advertising a higher score. The three bootstrapped
demonstrations are folded into the exported prompt so the artifact matches its number.

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

The recommendation is **derived, never invented**: it recommends the action that
sibling messages on the same indicator already received, and only when a sibling was
actually quarantined. On `login-verify.acme-portal.co` it names `d0e20c68` and
`41fe8ce8` and recommends quarantine, matching their 13 siblings. Ray recommends; Ray
cannot act, and says so.

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

The same discipline caught my worst mistake, but late: a repository-wide secret scan
on the final pass found that a live API key had reached four committed transcripts
(§6, defect 6). A scan I should have been running from the first commit, not the last.

Full session history, including my wrong turns, is in
`docs/tasks/ray-email-threat-investigator/conversation.md`. It records the badly framed
questions I asked, a decision I reversed, seven numbers I got wrong and corrected by
querying, and one process failure where I wrote a 500-line plan without showing it to
the reviewer.

---

## 6. Defects found by running the thing

Five, in order. I list them because which defects you find is a fact about how you
work.

1. **The grounding verifier could be forged by its own input** (§5). Found by a
   subagent auditing its own draft.
2. **`NULL` versus empty string** (§5). Found by a subagent distrusting my docs.
3. **Sub-agent tools ran on worker threads.** `deepagents` invokes tools off the main
   thread and a sqlite3 connection is thread-bound. Found by the first live run.
4. **The portal returned 500 on every question.** Three tool wrappers built their
   trace arguments with `locals()` — and **inside a closure `locals()` also returns the
   referenced free variables**, so `ctx`, holding a `sqlite3.Connection`, reached the
   JSON serializer. Found by the reviewer clicking the UI.
5. **The evidence panel showed one row of a seven-row result**, and **the subagents
   were never attributed and barely called.** The trace preview was capped at 600
   characters; and `_emit` never passed a subagent, because all three specialists
   shared one set of tool objects — so `subagents_used` was always empty and no
   transcript contained a single delegation. Found by the reviewer asking for a badge.

6. **A live API key reached four committed transcripts.** The `locals()` defect in 4
   had a second consequence I did not see at the time: it recorded
   `repr(RayContext)` into the trace, and that repr contained
   `Config(api_key='sk-ant-…')`. Four transcripts and four commits carried a working
   credential. Found by a repository-wide secret scan while verifying a clean
   checkout, on the last pass before handover.

   The brief says "Don't commit your API key." I did, transitively, through a
   debugging convenience. Three layers now stand between a credential and a trace:
   tool arguments are built explicitly (no `locals()` anywhere in `src/ray`);
   `Config.api_key` is declared `repr=False`, so the same mistake would be harmless if
   it recurred; and `trace.scrub` redacts credential shapes from every string entering
   a trace, because a transcript is a file that gets shared. Four tests guard it,
   including two that fail the suite if any committed transcript contains a credential
   or a `RayContext` repr.

   The affected transcripts were re-recorded and the key was purged from git history.
   **The key still had to be rotated**, because it had existed in commits — a rewrite
   removes the object, not the exposure.

**The pattern in 4 and 5 is the lesson.** Both were in the interface layer and both
were invisible to a passing suite, because the portal tests used a fake Ray whose tools
recorded nothing. **A component test that fakes its collaborator proves the component,
not the seam.** The regression tests now drive every registered tool through the real
wrappers, and a further test fails if a new tool escapes that check.

Defect 5 also had a consequence beyond display: a compiled adjudicator prompt is worth
nothing if the adjudicator is never invoked. Before the fix, it effectively was not.

---

## 7. What is not finished, and known limits

Stated plainly rather than left to be discovered.

1. **The model is not the one the brief specifies.** §0.
2. **Delegation is unreliable.** `deepagents` dispatch is model-driven — the model
   decides whether to call `task`. Haiku now delegates on the verdict trigger, but
   still answers *"who else got hit by the campaign?"* directly instead of calling
   `campaign-correlator`. Defensible, since `domain_intel` and `entity_graph` return
   the full picture, but not what the prompt asks. I stopped tuning rather than chase a
   small model.
3. **Citation discipline needs a safety net.** Haiku reliably writes a good answer and
   then cites it badly — inventing `[domain_intel]`, a tool name, as if it were a row.
   A failed grounding check therefore triggers **one corrective pass** asking Ray to
   re-cite from tool output already in its context, findings unchanged. The transcript
   records that the correction happened rather than hiding it. This is a workaround for
   a small model, not something I would claim as elegant.
4. **Ray under-cites.** Answers pass the grounding check but carry fewer citations than
   claims. Nothing verifies that *every* claim is cited, only that every citation
   resolves.
5. **The DSPy sets are small** — 12 agreement and 8 adversarial examples. The 8 are
   every wrong row in the corpus, so that half cannot grow; the agreement half could.
6. **The time budget.** The brief sets 3 hours. Exploration, design and tier 1 fit
   roughly that; tiers 2 and 3 did not. The reviewer chose to continue. `plan.md`
   section 5 states the overrun openly and orders the work into three cut lines, so a
   stop at any tier leaves a coherent submission.
7. **`entity_graph` layout is deterministic, not pretty.** Columns by node kind. No
   physics, no library, because the page must stay self-contained.

---

## 8. What I would do next

In the order I would actually do it.

1. **Make delegation deterministic where it matters.** Route on the question, not on
   the model's mood: a verdict-questioning phrasing should always reach the
   adjudicator. That also makes the compiled prompt reliably load-bearing.
2. **Verify claim coverage, not just citation validity.** Split the answer into
   claims and check that each carries a citation. That closes limit 4 and removes the
   need for the corrective pass in limit 3.
3. **Sweep the whole corpus with the adjudicator and rank the disagreements.** Ray can
   already disagree with one verdict on request. Running it over all 2288 and surfacing
   the strongest divergences turns a question-answering tool into a detection-quality
   audit — the highest-value thing on this list.
4. **Feed the audit back into detection.** The eight wrong rows share structure: a
   clean authentication pass on a lookalike domain, and an unscanned link identical to
   a known-malicious one. Both are analyzer rules, not agent rules.
5. **Ingest click and EDR telemetry.** The one gap Ray cannot reason around today.
   Scenario 3 is where the analyst feels it.
6. **Then re-run the DSPy compile with a larger agreement set and a stronger
   optimizer** (`MIPROv2`), which rewrites instructions rather than only adding
   demonstrations.

---

## 9. Where to look

| Question | File |
|---|---|
| Purpose, scope, terminology | `docs/vision.md` |
| The design and the acceptance criteria | `docs/tasks/ray-email-threat-investigator/plan.md` |
| What the database actually contains | same, section 2 |
| Implementation log and every defect | same folder, `progress.md` |
| **How the design was reached, honestly** | same folder, `conversation.md` |
| The ten decisions, each with alternatives | `docs/decisions/` |
| Rules for a coding agent in this repo | `AGENTS.md` |
| Commands and environment | `README.md` |
| Recorded runs | `transcripts/` |
| The compile report | `prompts/adjudicator.report.md` |
