"""Build-time compile of the verdict-reviewer prompt with DSPy.

Run with:

    python -m ray.dspy.compile_reviewer [--dry-run] [--n-agreement N]

ADR-009 and plan.md 4.5b hold the decision. This script:

1. Reads the database and builds the two label sets from `metric.py` (the
   agreement set, sampled and balanced, and the held-out adversarial set).
2. Evaluates the hand-written baseline core
   (`prompts.VERDICT_REVIEWER_REASONING`) on both sets with the two-sided metric.
3. Optimizes with a cheap DSPy optimizer, bootstrapping demonstrations from the
   agreement set only — never from the adversarial set, which stays held out.
4. Evaluates the optimized program the same way.
5. Writes `prompts/reviewer.compiled.json` (the artifact `subagents.py` loads)
   and `prompts/reviewer.report.md` (a before/after table).

The artifact holds the optimized core, with its bootstrapped demonstrations, wrapped
in the fixed blocks by `prompts.with_fixed_blocks`. The citation rules, the
untrusted-content rules, and the case-note contract are never optimized, because IR1
and IR4 do not bend to a metric (ADR-012).

Nothing in the serving path imports this module or the `dspy` package (IR8).
`import dspy` happens only inside this file, never in `metric.py`.

Timebox: 35 minutes (ADR-009). If the DSPy integration does not complete, this
script still writes the artifact with the hand-written prompt as `prompt`, the
measured baseline as `score`, and an explicit `"optimizer": "none — ..."` field,
so nothing is overstated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

# DSPy reaches Anthropic through litellm, which reads ANTHROPIC_API_KEY. Copy the
# key before anything else touches the environment (ADR-005, IR6). Never print it.
if os.environ.get("OCEAN_ANTHROPIC_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["OCEAN_ANTHROPIC_KEY"]

from .. import config as config_module  # noqa: E402
from .. import db  # noqa: E402
from .. import prompts  # noqa: E402
from . import metric  # noqa: E402

MODEL_NAME = "claude-haiku-4-5-20251001"
LM_ID = f"anthropic/{MODEL_NAME}"

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPILED_PATH = REPO_ROOT / "prompts" / "reviewer.compiled.json"
REPORT_PATH = REPO_ROOT / "prompts" / "reviewer.report.md"

METRIC_DESCRIPTION = (
    "Two-sided (ADR-009): score_verdict grades a predicted verdict against an "
    "expected one on a 3-point scale (exact match 1.0, suspicious-vs-malicious "
    "0.5, crossing the safe/not-safe boundary 0.0). The combined score weights "
    "the 8 held-out adversarial rows (recorded verdict is wrong) at 60% and a "
    "balanced sample of the recorded decisions (agreement set) at 40%, so a "
    "constant 'safe' answer — which would score over 98% on agreement alone —"
    " scores 0.0 on the adversarial half."
)


def _build_label_sets(conn, n_agreement: int):
    agreement = metric.agreement_examples(conn, limit=n_agreement)
    adversarial = [
        {"message_id": message_id, "verdict": verdict}
        for message_id, verdict in metric.ADVERSARIAL.items()
    ]
    return agreement, adversarial


def _write_artifact(payload: dict) -> None:
    COMPILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPILED_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_report(report_text: str) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")


def _fallback_payload(reason: str, baseline_result: dict | None, n_agreement: int, n_adversarial: int) -> dict:
    score = baseline_result["combined"] if baseline_result else 0.0
    return {
        "prompt": prompts.VERDICT_REVIEWER_PROMPT,
        "score": score,
        "baseline_score": score,
        "metric": METRIC_DESCRIPTION,
        "model": MODEL_NAME,
        "n_agreement": n_agreement,
        "n_adversarial": n_adversarial,
        "optimizer": f"none — baseline only, DSPy compile did not complete ({reason})",
    }


def _report_table(baseline: dict, compiled: dict | None) -> str:
    lines = [
        "# Reviewer compile report",
        "",
        f"Model: `{MODEL_NAME}`",
        "",
        f"Metric: {METRIC_DESCRIPTION}",
        "",
        "| | agreement | adversarial | combined |",
        "|---|---|---|---|",
        f"| baseline (hand-written) | {baseline['agreement']:.3f} | {baseline['adversarial']:.3f} | {baseline['combined']:.3f} |",
    ]
    if compiled is not None:
        lines.append(
            f"| compiled (DSPy) | {compiled['agreement']:.3f} | {compiled['adversarial']:.3f} | {compiled['combined']:.3f} |"
        )
    else:
        lines.append("| compiled (DSPy) | — | — | — (did not complete) |")
    lines.append("")
    lines.append(f"n_agreement = {baseline['n_agreement']}, n_adversarial = {baseline['n_adversarial']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the label sets and print their sizes. No model calls.",
    )
    parser.add_argument(
        "--n-agreement",
        type=int,
        default=24,
        help="Target size of the agreement set (balanced across verdicts).",
    )
    parser.add_argument(
        "--max-demos",
        type=int,
        default=4,
        help="Max bootstrapped few-shot demonstrations for the optimizer.",
    )
    args = parser.parse_args(argv)

    cfg = config_module.load_config()
    conn = db.connect_readonly(cfg.db_path)

    agreement, adversarial = _build_label_sets(conn, args.n_agreement)
    print(f"Agreement examples: {len(agreement)}")
    print(f"Adversarial examples: {len(adversarial)} (held out of bootstrapping)")

    if args.dry_run:
        print("--dry-run: wiring checked, no model calls made.")
        return 0

    if not cfg.has_key:
        print(f"No {config_module.KEY_VAR} set. Writing fallback artifact (hand-written prompt).")
        payload = _fallback_payload("no API key available", None, len(agreement), len(adversarial))
        _write_artifact(payload)
        return 0

    # Rough LM-call budget: baseline eval + optimizer bootstrap eval + compiled eval.
    n_eval = len(agreement) + len(adversarial)
    est_calls = n_eval * 2 + len(agreement)  # baseline + compiled evals + bootstrap attempts
    print(f"Estimated LM calls for this run: ~{est_calls} (on {MODEL_NAME})")

    import dspy  # build-time only import (IR8) — never imported at request time

    lm = dspy.LM(LM_ID, max_tokens=2048)
    dspy.configure(lm=lm)

    class ReviewVerdict(dspy.Signature):
        evidence: str = dspy.InputField(desc="The evidence bundle for one message.")
        verdict: str = dspy.OutputField(desc="One of: safe, suspicious, malicious.")
        reasoning: str = dspy.OutputField(desc="Why this verdict follows from the evidence.")

    ReviewVerdict.__doc__ = prompts.VERDICT_REVIEWER_REASONING

    class Reviewer(dspy.Module):
        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(ReviewVerdict)

        def forward(self, evidence: str):
            return self.predict(evidence=evidence)

    def to_examples(rows):
        out = []
        for row in rows:
            evidence = metric.build_evidence(conn, row["message_id"])
            out.append(dspy.Example(evidence=evidence, verdict=row["verdict"]).with_inputs("evidence"))
        return out

    agreement_ds = to_examples(agreement)
    adversarial_ds = to_examples(adversarial)

    def dspy_metric(example, prediction, trace=None):
        return metric.score_verdict(getattr(prediction, "verdict", ""), example.verdict)

    def evaluate(program, examples):
        scores = []
        for ex in examples:
            try:
                pred = program(evidence=ex.evidence)
                scores.append(metric.score_verdict(getattr(pred, "verdict", ""), ex.verdict))
            except Exception:
                traceback.print_exc()
                scores.append(0.0)
        return scores

    print("Evaluating baseline (hand-written prompt)...")
    baseline_program = Reviewer()
    baseline_agreement_scores = evaluate(baseline_program, agreement_ds)
    baseline_adversarial_scores = evaluate(baseline_program, adversarial_ds)
    baseline_result = metric.two_sided_score(baseline_agreement_scores, baseline_adversarial_scores)
    print("Baseline:", baseline_result)

    # Write a fallback artifact now, so a crash in the optimizer step still
    # leaves a valid, honest artifact behind (ADR-009 timebox fallback).
    _write_artifact(
        _fallback_payload(
            "optimizer step not yet completed", baseline_result, len(agreement), len(adversarial)
        )
    )

    try:
        from dspy.teleprompt import BootstrapFewShot

        optimizer = BootstrapFewShot(
            metric=dspy_metric,
            max_bootstrapped_demos=args.max_demos,
            max_labeled_demos=args.max_demos,
        )
        print("Optimizing (bootstrapping demos from the agreement set only)...")
        optimized_program = optimizer.compile(Reviewer(), trainset=agreement_ds)

        print("Evaluating optimized program...")
        opt_agreement_scores = evaluate(optimized_program, agreement_ds)
        opt_adversarial_scores = evaluate(optimized_program, adversarial_ds)
        opt_result = metric.two_sided_score(opt_agreement_scores, opt_adversarial_scores)
        print("Optimized:", opt_result)

        # `Reviewer.predict` is a ChainOfThought, which wraps its own inner
        # `predict` (a plain dspy.Predict) that holds the final signature.
        inner_predict = optimized_program.predict.predict
        base_instructions = (
            inner_predict.signature.instructions or prompts.VERDICT_REVIEWER_REASONING
        )

        # BootstrapFewShot's improvement lives in the bootstrapped demonstrations,
        # not in the instructions text (this optimizer never rewrites the
        # instructions). Fold the demos into the exported prompt string, so the
        # artifact actually carries what the optimizer learned — otherwise
        # `subagents.py` would load a prompt indistinguishable from the baseline
        # despite a higher recorded score.
        demos = list(getattr(inner_predict, "demos", []) or [])
        final_instructions = base_instructions
        if demos:
            demo_blocks = []
            for demo in demos:
                evidence = getattr(demo, "evidence", "")
                verdict = getattr(demo, "verdict", "")
                reasoning = getattr(demo, "reasoning", "")
                demo_blocks.append(
                    f"Evidence:\n{evidence}\n\nReasoning: {reasoning}\nVerdict: {verdict}"
                )
            final_instructions = (
                base_instructions
                + "\n\n## Worked examples (bootstrapped from the agreement set)\n\n"
                + "\n\n---\n\n".join(demo_blocks)
            )

        payload = {
            # The fixed blocks go on last, and no optimizer touches them (ADR-012).
            "prompt": prompts.with_fixed_blocks(final_instructions),
            "core": final_instructions,
            "score": opt_result["combined"],
            "baseline_score": baseline_result["combined"],
            "metric": METRIC_DESCRIPTION,
            "model": MODEL_NAME,
            "n_agreement": len(agreement),
            "n_adversarial": len(adversarial),
            "optimizer": f"BootstrapFewShot(max_demos={args.max_demos})",
        }
        _write_artifact(payload)
        _write_report(_report_table(baseline_result, opt_result))
        print(f"Wrote {COMPILED_PATH}")
        print(f"Wrote {REPORT_PATH}")
    except Exception as error:
        print(f"Optimizer step failed: {error}")
        traceback.print_exc()
        payload = _fallback_payload(str(error), baseline_result, len(agreement), len(adversarial))
        _write_artifact(payload)
        _write_report(_report_table(baseline_result, None))
        print("Wrote fallback artifact (baseline only).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
