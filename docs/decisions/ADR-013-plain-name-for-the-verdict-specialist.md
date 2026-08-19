# ADR-013: The verdict specialist is named `verdict-reviewer`, in plain English

**Date:** 2026-08-19
**Status:** accepted
**Amends:** ADR-008 and ADR-009, which named the specialist `verdict-adjudicator`, and
ADR-012, which named its artifact `adjudicator.compiled.json`.

## Context

The specialist that forms an independent verdict was called `verdict-adjudicator`. The
word is precise. An adjudicator, from Latin *adjudicare*, is the party that formally
settles a dispute, which is what the specialist does to a recorded verdict.

Two facts in this repository argue against the word all the same.

1. **`AGENTS.md` section 5 requires Simplified Technical English.** A controlled
   vocabulary exists to keep a document readable by a reader whose first language is not
   English. `review` and `check` belong to such a vocabulary. `adjudicate` does not.
   The project held the word only because `docs/vision.md` section 3 defines it, which
   is an exemption, not a justification.
2. **The analyst asked what the word means.** A term that a reader has to look up costs
   more than the precision it buys, and `docs/vision.md` section 3 exists to remove that
   cost rather than to license it.

The rename is not free. The specialist name appears 179 times, in 3 filenames, in 2
README commands, inside the committed compiled artifact, and 23 times in the recorded
transcripts. So the rename requires the compile to run again and the transcripts to be
recorded again.

**One term collides.** This repository already used "reviewer" for the person grading
the submission, and `conversation.md` of the first task records that ambiguity being
found and settled once before, under item E2.

## Decision

**The specialist is `verdict-reviewer`. Nothing else in this repository is a reviewer.**

1. **The name.** `verdict-reviewer`, always hyphenated when it names the specialist.
   `VERDICT_REVIEWER_PROMPT` and `VERDICT_REVIEWER_REASONING` in `prompts.py`,
   `compile_reviewer.py` for the build step, and `prompts/reviewer.compiled.json` with
   `prompts/reviewer.report.md` for its artifacts.

2. **The collision is removed, not tolerated.** The person grading the submission is
   now **a reader** everywhere: in `README.md`, `NOTES.md`, `pyproject.toml`, ADR-006,
   ADR-009, ADR-010, and ADR-012. "Reviewer" now has exactly one meaning in this
   repository, which is what `docs/vision.md` section 3 requires. Where prose means the
   specialist and the sentence could be read either way, the full `verdict-reviewer`
   appears rather than the bare noun.

3. **Earlier records are updated in place.** ADR-008, ADR-009, and ADR-012 now use the
   new name, and this record states that they were changed. The alternative — leaving
   the old name in the records that introduced it — would put two names for one thing in
   the repository, which is the rule this rename exists to serve. The decisions those
   records made are untouched; only the noun changed.

4. **The measurement is taken again.** The compiled artifact stores the prompt core,
   and that core names the specialist, so the rename means a recompile rather than a
   text edit. `NOTES.md` and `prompts/reviewer.report.md` carry the newly measured
   number, whatever it is, and not the number from the run before the rename. Editing a
   score to survive a rename would be the one thing this project cannot do.

5. **The transcripts are recorded again**, so no committed deliverable names a
   specialist that no longer exists.

## Alternatives Considered

**Keep `verdict-adjudicator`.** Rejected. It is precise and defined, and the analyst
still had to ask what it meant, which is the evidence that the definition was not doing
its job.

**`verdict-checker`.** Rejected, though it is the plainest option and it avoids the
"reviewer" collision entirely. A checker validates against a rule; this specialist forms
an independent verdict and weighs an analyst's stated reason on its merits. The plainer
word describes a smaller job than the one the specialist does.

**`second-opinion`.** Rejected. It is the closest to how an analyst would speak, and it
reads badly as an identifier in a tool call. "Opinion" also sits against product
principle 1, where every Ray statement rests on a row.

**Rename the documents only, and leave the identifiers.** Rejected. A reader would meet
one word in `NOTES.md` and a different one in the portal badge and the tool-call log.

## Consequences

**Positive.** The roster now reads in plain English: a triage officer, an authentication
forensics analyst, a campaign correlator, a verdict reviewer, and an incident responder.
"Reviewer" has one meaning where it previously had two, which repairs an ambiguity that
this repository had already found once. The vocabulary now matches the writing standard
that `AGENTS.md` sets, rather than relying on an exemption from it.

**Negative.** The recompile produces a fresh number, so the score in `NOTES.md` moves
for a reason that has nothing to do with prompt quality. Every record that named the old
specialist changed, so a reader of the git history sees a large rename commit across
ADRs. Anyone holding an older checkout has an artifact filename that no longer resolves;
the fallback covers it, and startup reports the fallback per specialist.

**Follow-up.** `docs/vision.md` section 3 owns the term. If another Latinate term in that
table makes a reader stop — `divergence` is the next candidate, where `disagreement`
would serve — the same test applies: a term that needs a lookup costs more than its
precision.
