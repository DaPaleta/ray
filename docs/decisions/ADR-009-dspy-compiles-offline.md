# ADR-009: DSPy compiles the adjudicator prompt offline, into a static artifact

**Date:** 2026-08-19
**Status:** accepted

## Context

The analyst wants the project to show production-grade prompt engineering, and
chose DSPy for it. DSPy optimizes a prompt against data and a metric, rather than
by hand.

Two constraints shape how much DSPy this project can carry.

1. **The brief sets a 3-hour budget.** An optimizer that runs inside the request
   path adds latency, a dependency, and a failure mode to every turn.
2. **An optimizer needs a metric, and a metric needs labels.** Without labels,
   DSPy optimizes against an opinion, and the exercise proves nothing.

The database supplies real labels, and it supplies them on both sides:

- **The agreement set.** 2288 recorded decisions. A correct adjudicator agrees
  with the vast majority of them.
- **The adversarial set.** Eight rows where the recorded verdict is wrong: the 5
  released `quaystone-billing-portal.com` messages, the 2 payslip false negatives
  `d0e20c68` and `41fe8ce8`, and the CFO impersonation `276266c0`. A correct
  adjudicator **disagrees** with each one.

A metric that rewards agreement alone would score a constant "safe" answer at over
98 percent. The two-sided metric is what makes the target real.

## Decision

**Compile offline. Serve a static artifact.**

1. `src/ray/dspy/compile_adjudicator.py` runs at build time. It reads the
   database, builds the two label sets, defines the metric, and optimizes the
   verdict-adjudicator prompt.
2. The compile writes `prompts/adjudicator.compiled.json`. That file is committed.
3. `agent.py` loads the artifact and places the prompt into the
   verdict-adjudicator subagent from ADR-008. Nothing imports DSPy at request
   time.
4. `requirements.txt` excludes DSPy. `requirements-dev.txt` holds it. A reviewer
   who only runs Ray never installs it.
5. When the artifact is absent, Ray falls back to the hand-written prompt and says
   so at startup. The fallback is a supported state, not a crash.

**The metric is two-sided.** It scores the verdict against the agreement set, and
it scores correct disagreement against the adversarial set. The adversarial set is
held out of any few-shot selection, so a compiled prompt cannot pass by having
memorized the eight rows.

**The measurement ships regardless.** `NOTES.md` carries a before-and-after table:
the hand-written prompt against the same metric, and the compiled prompt against
it. This is the part that demonstrates prompt engineering, and it holds whether
or not the optimizer improves the score.

**Timebox: 35 minutes.** If the DSPy integration is not working by then, the
project ships the evaluation harness with the hand-written prompt, and `NOTES.md`
reports the metric and the score without the optimizer. Risk R10 records this.

## Alternatives Considered

**Run DSPy inside the serving path.** Rejected. It puts an optimizer dependency
and its latency into every request, for a prompt that does not change between
requests. A prompt is a build artifact, so it belongs in a build step.

**Compile the natural-language to tool-argument router as well.** Rejected. The
router has no ground-truth labels, so its metric would rest on an opinion, and it
roughly doubles the compile time. Two compiled modules with one good metric is
worse than one compiled module with one good metric.

**Hand-write the prompt and skip DSPy.** Rejected as the target, kept as the
fallback. The evaluation harness is the load-bearing part, so the fallback keeps
most of the value at much lower risk.

**Optimize against the recorded verdicts alone.** Rejected. A constant "safe"
answer scores over 98 percent on that metric, so it would reward exactly the
failure mode that the eight adversarial rows expose.

## Consequences

**Positive.** The serving path stays lean, and a clean checkout needs one
`requirements.txt` and one command, as brief requirement 1 asks. The prompt becomes
a versioned, reviewable, committed artifact. The two-sided metric gives an
objective number to report, so the prompt work is measured rather than asserted.
Haiku makes the optimizer loop cheap enough to run more than once.

**Negative.** The compiled artifact can drift from the source prompt if someone
edits one and not the other. A compiled prompt is less readable than a
hand-written one, so the repository keeps both and `NOTES.md` explains the
relationship. DSPy is the highest-risk item in the plan, and the timebox exists
because of that.

**Follow-up.** Commit `prompts/adjudicator.compiled.json` together with the score
that produced it, so a reader can tell which artifact the reported number belongs
to. Record the metric definition in `NOTES.md`, not only in code.
