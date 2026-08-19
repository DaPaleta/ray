"""Build-time compile of the campaign-correlator prompt with DSPy.

Run with:

    python -m ray.dspy.compile_correlator [--dry-run] [--candidates N] [--trials N]

ADR-012 holds the decision. This script:

1. Builds the two label sets from `correlation.py` — 10 agreement seeds, and 2
   adversarial seeds held out of the optimizer.
2. Scores the three shortcut baselines, which need no model at all: a `campaign_id`
   join, a flagged-only filter, and a greedy "name everything" answer.
3. Evaluates the hand-written baseline core
   (`prompts.CAMPAIGN_CORRELATOR_REASONING`) on both sets.
4. Optimizes with MIPROv2, configured for **zero demonstrations**, so it rewrites the
   instruction text and adds no few-shot examples. That choice is deliberate: one
   correlation demonstration carries a candidate list of up to 38 messages, so a
   few-shot artifact would add tens of thousands of characters to every request. The
   reviewer keeps BootstrapFewShot, where one demonstration is one evidence bundle.

   COPRO was the first choice and does not work here: it asks the provider for `n`
   completions in one call, and litellm rejects `n` for Anthropic models.
5. Evaluates the optimized program the same way.
6. Writes `prompts/correlator.compiled.json` and `prompts/correlator.report.md`.

The artifact holds the optimized core wrapped in the fixed blocks by
`prompts.with_fixed_blocks`. The citation rules, the untrusted-content rules, and the
case-note contract are never optimized, because IR1 and IR4 do not bend to a metric.

Nothing in the serving path imports this module or the `dspy` package (IR8).
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
from . import correlation  # noqa: E402
from .metric import two_sided_score  # noqa: E402

MODEL_NAME = "claude-haiku-4-5-20251001"
LM_ID = f"anthropic/{MODEL_NAME}"

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPILED_PATH = REPO_ROOT / "prompts" / "correlator.compiled.json"
REPORT_PATH = REPO_ROOT / "prompts" / "correlator.report.md"

METRIC_DESCRIPTION = (
    "Two-sided over message-identifier sets (ADR-012): score_membership grades a "
    "predicted member set against the expected set by F1, so recall punishes a member "
    "missed and precision punishes a message wrongly included. A missing required "
    "identifier sets the score to 0.0. The combined score weights the 2 held-out "
    "adversarial seeds at 60% and the 10 agreement seeds at 40%. The adversarial half "
    "refuses every single-field shortcut: a campaign_id join misses 93bae03b, a "
    "flagged-only filter misses the recorded-safe members d0e20c68 and 41fe8ce8, and a "
    "greedy answer loses precision on a sender domain that sends 154 messages of which "
    "7 are the activity."
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _artifact(core: str, score: float, baseline: float, optimizer: str,
              n_agreement: int, n_adversarial: int, shortcuts: dict) -> dict:
    return {
        "prompt": prompts.with_fixed_blocks(core),
        "core": core,
        "score": score,
        "baseline_score": baseline,
        "shortcut_baselines": shortcuts,
        "metric": METRIC_DESCRIPTION,
        "model": MODEL_NAME,
        "n_agreement": n_agreement,
        "n_adversarial": n_adversarial,
        "optimizer": optimizer,
    }


def _report(baseline: dict, compiled: dict | None, shortcuts: dict, optimizer: str) -> str:
    lines = [
        "# Correlator compile report",
        "",
        f"Model: `{MODEL_NAME}`",
        "",
        f"Optimizer: {optimizer}",
        "",
        f"Metric: {METRIC_DESCRIPTION}",
        "",
        "## Shortcut baselines — no model call",
        "",
        "Each row is a correlator that needs no model. The metric exists to refuse them.",
        "",
        "| shortcut | agreement | adversarial | combined |",
        "|---|---|---|---|",
    ]
    for name, result in shortcuts.items():
        lines.append(
            f"| {name} | {result['agreement']:.3f} | {result['adversarial']:.3f} | "
            f"{result['combined']:.3f} |"
        )
    lines += [
        "",
        "## Prompt",
        "",
        "| | agreement | adversarial | combined |",
        "|---|---|---|---|",
        f"| baseline (hand-written core) | {baseline['agreement']:.3f} | "
        f"{baseline['adversarial']:.3f} | {baseline['combined']:.3f} |",
    ]
    if compiled is not None:
        lines.append(
            f"| compiled (DSPy) | {compiled['agreement']:.3f} | "
            f"{compiled['adversarial']:.3f} | {compiled['combined']:.3f} |"
        )
    else:
        lines.append("| compiled (DSPy) | — | — | — (did not complete) |")
    lines += [
        "",
        f"n_agreement = {baseline['n_agreement']}, n_adversarial = "
        f"{baseline['n_adversarial']}",
        "",
        "The bar to beat is the strongest shortcut, not zero. Read the two tables "
        "together.",
    ]
    if compiled is not None:
        delta = compiled["combined"] - baseline["combined"]
        if delta > 0.001:
            lines += ["", f"The compiled prompt gains {delta:+.3f} on the combined score."]
        elif baseline["combined"] >= 0.999:
            lines += [
                "",
                "**No headroom.** The hand-written core already scores 1.000 on both "
                "halves, so no instruction can beat it on this metric. The optimizer "
                "ran and kept the incumbent. What the measurement shows is that the "
                "three shortcuts fail and the hand-written prompt does not. The metric "
                "was not hardened afterwards to manufacture a gain, because tuning a "
                "metric towards a wanted result is the failure ADR-012 exists to "
                "prevent.",
            ]
        else:
            lines += [
                "",
                f"The compiled prompt does not beat the hand-written core "
                f"({delta:+.3f}). The artifact records both scores.",
            ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Build the label sets and score the shortcuts. No model calls.")
    parser.add_argument("--candidates", type=int, default=6,
                        help="MIPROv2 instruction candidates to propose.")
    parser.add_argument("--trials", type=int, default=8,
                        help="MIPROv2 optimization trials.")
    parser.add_argument("--threads", type=int, default=8, help="Evaluation threads.")
    args = parser.parse_args(argv)

    cfg = config_module.load_config()
    conn = db.connect_readonly(cfg.db_path)

    agreement_cases = correlation.build_cases(conn, correlation.AGREEMENT_SEEDS)
    adversarial_cases = correlation.build_cases(conn, correlation.ADVERSARIAL_SEEDS)
    print(f"Agreement seeds: {len(agreement_cases)}")
    print(f"Adversarial seeds: {len(adversarial_cases)} (held out of the optimizer)")

    shortcuts = {
        "campaign_id join": correlation.campaign_id_baseline(conn),
        "flagged messages only": correlation.flagged_only_baseline(conn),
        "name every candidate": correlation.everything_baseline(conn),
    }
    for name, result in shortcuts.items():
        print(f"  shortcut {name}: combined {result['combined']:.3f} "
              f"(adversarial {result['adversarial']:.3f})")

    if args.dry_run:
        print("--dry-run: wiring checked, no model calls made.")
        return 0

    if not cfg.has_key:
        print(f"No {config_module.KEY_VAR} set. Writing fallback artifact (hand-written core).")
        _write(COMPILED_PATH, json.dumps(_artifact(
            prompts.CAMPAIGN_CORRELATOR_REASONING, 0.0, 0.0,
            "none — baseline only, no API key available",
            len(agreement_cases), len(adversarial_cases), shortcuts), indent=2) + "\n")
        return 0

    import dspy  # build-time only import (IR8) — never imported at request time

    lm = dspy.LM(LM_ID, max_tokens=3000)
    dspy.configure(lm=lm)

    class CorrelateActivity(dspy.Signature):
        evidence: str = dspy.InputField(
            desc="A seed indicator and the candidate messages that match it."
        )
        rationale: str = dspy.OutputField(
            desc="Which shared indicator ties each member in, and why the others are out."
        )
        member_ids: str = dspy.OutputField(
            desc="Comma-separated 8-character ids of the messages in one attacker "
                 "activity. Write 'none' when no activity exists behind the seed."
        )

    CorrelateActivity.__doc__ = prompts.CAMPAIGN_CORRELATOR_REASONING

    class Correlator(dspy.Module):
        def __init__(self):
            super().__init__()
            self.predict = dspy.Predict(CorrelateActivity)

        def forward(self, evidence: str):
            return self.predict(evidence=evidence)

    def to_examples(cases):
        return [
            dspy.Example(
                evidence=case.evidence,
                expected_ids=",".join(sorted(case.expected)),
                require_ids=",".join(sorted(case.require)),
                shown_ids=",".join(case.shown),
            ).with_inputs("evidence")
            for case in cases
        ]

    def _split(value: str) -> set[str]:
        return {part for part in (value or "").split(",") if part}

    def dspy_metric(example, prediction, trace=None):
        predicted = correlation.parse_member_ids(
            getattr(prediction, "member_ids", "") or ""
        ) & _split(example.shown_ids)
        return correlation.score_membership(
            predicted,
            frozenset(_split(example.expected_ids)),
            frozenset(_split(example.require_ids)),
        )

    def evaluate(program, examples):
        scores = []
        for example in examples:
            try:
                prediction = program(evidence=example.evidence)
                scores.append(dspy_metric(example, prediction))
            except Exception:
                traceback.print_exc()
                scores.append(0.0)
        return scores

    agreement_ds = to_examples(agreement_cases)
    adversarial_ds = to_examples(adversarial_cases)

    print("Evaluating baseline (hand-written core)...")
    baseline_program = Correlator()
    baseline_result = two_sided_score(
        evaluate(baseline_program, agreement_ds),
        evaluate(baseline_program, adversarial_ds),
    )
    print("Baseline:", baseline_result)

    # Write an honest baseline-only artifact now, so a crash in the optimizer leaves a
    # valid artifact behind rather than a stale or absent one (ADR-012, risk R18).
    _write(COMPILED_PATH, json.dumps(_artifact(
        prompts.CAMPAIGN_CORRELATOR_REASONING, baseline_result["combined"],
        baseline_result["combined"], "none — optimizer step not yet completed",
        len(agreement_cases), len(adversarial_cases), shortcuts), indent=2) + "\n")

    optimizer_name = (
        f"MIPROv2(instruction-only, num_candidates={args.candidates}, "
        f"num_trials={args.trials})"
    )
    try:
        from dspy.teleprompt import MIPROv2

        print(f"Optimizing with {optimizer_name} on the agreement seeds only...")
        optimizer = MIPROv2(
            metric=dspy_metric,
            prompt_model=lm,
            task_model=lm,
            # Zero demos: the artifact must stay a prompt, not a few-shot corpus.
            max_bootstrapped_demos=0,
            max_labeled_demos=0,
            num_candidates=args.candidates,
            num_threads=args.threads,
            auto=None,
            verbose=False,
        )
        optimized = optimizer.compile(
            Correlator(),
            trainset=agreement_ds,
            num_trials=args.trials,
            minibatch=False,
            requires_permission_to_run=False,
        )

        print("Evaluating optimized program...")
        opt_result = two_sided_score(
            evaluate(optimized, agreement_ds), evaluate(optimized, adversarial_ds)
        )
        print("Optimized:", opt_result)

        core = (
            optimized.predict.signature.instructions
            or prompts.CAMPAIGN_CORRELATOR_REASONING
        )
        _write(COMPILED_PATH, json.dumps(_artifact(
            core, opt_result["combined"], baseline_result["combined"], optimizer_name,
            len(agreement_cases), len(adversarial_cases), shortcuts), indent=2) + "\n")
        _write(REPORT_PATH, _report(baseline_result, opt_result, shortcuts, optimizer_name))
        print(f"Wrote {COMPILED_PATH}")
        print(f"Wrote {REPORT_PATH}")
    except Exception as error:
        print(f"Optimizer step failed: {error}")
        traceback.print_exc()
        _write(COMPILED_PATH, json.dumps(_artifact(
            prompts.CAMPAIGN_CORRELATOR_REASONING, baseline_result["combined"],
            baseline_result["combined"], f"none — DSPy compile did not complete ({error})",
            len(agreement_cases), len(adversarial_cases), shortcuts), indent=2) + "\n")
        _write(REPORT_PATH, _report(baseline_result, None, shortcuts,
                                    f"{optimizer_name} — did not complete"))
        print("Wrote fallback artifact (baseline only).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
