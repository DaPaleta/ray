"""Tests for the DSPy adjudicator metric and label sets.

Must pass without DSPy installed and without a key (ADR-009, IR8). This module
imports only `ray.dspy.metric`, which imports no `dspy` at module level.
"""

from __future__ import annotations

from ray.dspy import metric

QUAYSTONE_IDS = (
    "c1e587141caa57faaa627f036324e876",
    "567beae60aa4532ba63cbad61e877af1",
    "a3b5e777c16358eba499a8e02e3caaa6",
    "5978f8ed9a4c53129adaeeb21db0a7ff",
    "0641802d9d225a48bf4a9fbe6623c13b",
)
PAYSLIP_IDS = (
    "d0e20c681476512bb2fd2fb32c280607",
    "41fe8ce8b2eb51c4b286f88fc855fd14",
)
CFO_ID = "276266c04c4256d0ad5b1f4f1294a2d6"


def test_adversarial_set_has_eight_rows():
    assert len(metric.ADVERSARIAL) == 8
    assert set(metric.ADVERSARIAL) == set(QUAYSTONE_IDS) | set(PAYSLIP_IDS) | {CFO_ID}


def test_adversarial_ids_recorded_as_safe(conn):
    for message_id in metric.ADVERSARIAL:
        row = conn.execute(
            "SELECT verdict FROM decisions WHERE message_id = ?", (message_id,)
        ).fetchone()
        assert row is not None, f"no decision row for {message_id}"
        assert row["verdict"] == "safe", (
            f"{message_id} recorded verdict is {row['verdict']!r}, expected 'safe' "
            "— that is what makes this row adversarial"
        )


def test_quaystone_rows_carry_override_and_attack_type(conn):
    for message_id in QUAYSTONE_IDS:
        row = conn.execute(
            "SELECT verdict, attack_type, overridden_by FROM decisions WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        assert row is not None
        assert row["verdict"] == "safe"
        assert row["attack_type"] == "credential_phishing"
        assert row["overridden_by"] == "tunde.okafor@acme.com"


def test_agreement_examples_excludes_adversarial_ids(conn):
    examples = metric.agreement_examples(conn, limit=40)
    ids = {row["message_id"] for row in examples}
    assert ids.isdisjoint(metric.ADVERSARIAL)


def test_agreement_examples_is_a_balanced_sample_not_thousands(conn):
    examples = metric.agreement_examples(conn, limit=40)
    assert 0 < len(examples) <= 60
    verdicts = {row["verdict"] for row in examples}
    # More than one verdict value should appear — not a 98%-safe dump.
    assert len(verdicts) > 1


def test_build_evidence_for_cfo_message_contains_required_facts(conn):
    evidence = metric.build_evidence(conn, CFO_ID)

    assert "rachel.adler@acme-robotics.com" in evidence
    assert "acme.com" in evidence
    assert "link-scanner" in evidence
    assert "did NOT run" in evidence


def test_build_evidence_for_cfo_message_does_not_leak_the_answer(conn):
    """The adjudicator must not see the answer it is being scored against.

    The recorded decision for this message is verdict='safe', attack_type=NULL,
    overridden_by=NULL, remediation.action='none'. We assert the evidence never
    states the recorded verdict as a verdict, never mentions the override
    field name, and never mentions the remediation action as an action.
    """
    evidence = metric.build_evidence(conn, CFO_ID)
    lowered = evidence.lower()

    # No mention of the decision/remediation/override vocabulary at all — the
    # evidence bundle is built only from messages/users/links/analyzer_results,
    # so these words (which only appear via decisions/remediations columns or
    # their labels) must be entirely absent.
    assert "overridden_by" not in lowered
    assert "override_reason" not in lowered
    assert "remediation" not in lowered
    assert "decision" not in lowered
    # The recorded verdict word "safe" must not appear anywhere (this message
    # has no links, so "scanned=no" style text cannot smuggle it in either).
    assert "safe" not in lowered


def test_build_evidence_for_payslip_shows_unscanned_and_malicious_siblings(conn):
    evidence = metric.build_evidence(conn, PAYSLIP_IDS[0])

    assert "unscanned" in evidence.lower()
    assert "malicious" in evidence.lower()
    assert "sibling" in evidence.lower()


def test_score_verdict_exact_match():
    assert metric.score_verdict("malicious", "malicious") == 1.0
    assert metric.score_verdict("safe", "safe") == 1.0


def test_score_verdict_adjacent():
    assert metric.score_verdict("suspicious", "malicious") == 0.5
    assert metric.score_verdict("malicious", "suspicious") == 0.5


def test_score_verdict_opposite():
    assert metric.score_verdict("safe", "malicious") == 0.0
    assert metric.score_verdict("malicious", "safe") == 0.0
    assert metric.score_verdict("safe", "suspicious") == 0.0


def test_score_verdict_tolerant_parsing():
    assert metric.score_verdict("Verdict: malicious", "malicious") == 1.0
    assert metric.score_verdict("After review, Verdict: suspicious.", "malicious") == 0.5


def test_two_sided_score_weights_adversarial_at_least_half():
    assert metric.ADVERSARIAL_WEIGHT >= 0.5

    result = metric.two_sided_score(agreement_results=[1.0], adversarial_results=[0.0])
    # Combined should track the adversarial score at least as much as agreement.
    assert result["combined"] <= 0.5 + 1e-9
    assert result["n_agreement"] == 1
    assert result["n_adversarial"] == 1


def test_constant_safe_baseline_scores_zero_on_adversarial():
    agreement_expected = ["safe", "safe", "malicious", "suspicious"]
    adversarial_expected = list(metric.ADVERSARIAL.values())

    result = metric.constant_safe_baseline(agreement_expected, adversarial_expected)

    assert result["adversarial"] == 0.0
    # A one-sided metric would score a constant "safe" answer very high. The
    # combined (two-sided) score must be well below a perfect 1.0.
    assert result["combined"] < 0.6
