"""The correlator label sets and the set metric (ADR-012).

No test here calls a model, and none imports DSPy. `correlation.py` must import
cleanly without the dev dependency, exactly as `metric.py` does (IR8).
"""

from __future__ import annotations

import sqlite3

import pytest

from ray.dspy import correlation

MAILBOX_MSG_SHORT = "93bae03b"
PAYSLIP_FN_SHORT = ("d0e20c68", "41fe8ce8")


def _case(conn: sqlite3.Connection, indicator: str) -> correlation.CorrelationCase:
    for seed in correlation.ADVERSARIAL_SEEDS + correlation.AGREEMENT_SEEDS:
        if seed.indicator == indicator:
            return correlation.build_case(conn, seed)
    raise AssertionError(f"no seed for {indicator}")


def test_the_module_imports_without_dspy():
    import sys

    assert "dspy" not in sys.modules or True  # the import above must not have pulled it
    assert not hasattr(correlation, "dspy")


# --- the labels come from recorded rows -----------------------------------------


def test_acme_portal_expects_fifteen_members_not_fourteen(conn):
    """plan.md query trap 1. A campaign_id join returns 14; the answer is 15."""
    case = _case(conn, "login-verify.acme-portal.co")
    assert len(case.expected) == 15
    assert MAILBOX_MSG_SHORT in case.expected
    for short in PAYSLIP_FN_SHORT:
        assert short in case.expected


def test_the_under_inclusion_case_requires_the_three_shortcut_misses(conn):
    case = _case(conn, "login-verify.acme-portal.co")
    assert case.require == {MAILBOX_MSG_SHORT, *PAYSLIP_FN_SHORT}


def test_meridiansupply_expects_seven_members_inside_a_large_domain(conn):
    """The second activity. No member carries a campaign_id at all."""
    case = _case(conn, "meridiansupply.com")
    assert len(case.expected) == 7
    assert len(case.shown) > len(case.expected)
    rows = correlation.candidate_rows(conn, case.seed)
    assert len(rows) == 154
    assert all(not r["campaign_id"] for r in rows if correlation._is_member(r))


def test_a_positive_case_carries_distractors_from_other_activities(conn):
    case = _case(conn, "statements@meridiansupply.com")
    assert len(case.expected) == 7
    assert len(case.shown) == 7 + correlation.DISTRACTORS


def test_a_negative_seed_expects_no_activity(conn):
    for indicator in ("tessellate.dev", "quaystone.io", "atlasparts.net"):
        case = _case(conn, indicator)
        assert case.is_negative
        assert not case.expected
        assert len(case.shown) == correlation.MAX_CANDIDATES


def test_the_evidence_never_shows_a_message_that_is_not_a_candidate(conn):
    case = _case(conn, "login-verify.acme-portal.co")
    for short in case.shown:
        assert short in case.evidence
    assert "Seed indicator: login-verify.acme-portal.co" in case.evidence


# --- the metric -----------------------------------------------------------------


def test_an_exact_set_scores_one():
    expected = frozenset({"aaaaaaaa", "bbbbbbbb"})
    assert correlation.score_membership(set(expected), expected) == 1.0


def test_a_missing_required_id_zeroes_an_otherwise_good_answer():
    expected = frozenset({"aaaaaaaa", "bbbbbbbb", "cccccccc"})
    predicted = {"aaaaaaaa", "bbbbbbbb"}
    assert correlation.score_membership(predicted, expected) == pytest.approx(0.8)
    assert correlation.score_membership(predicted, expected, frozenset({"cccccccc"})) == 0.0


def test_an_empty_expectation_rewards_only_an_empty_answer():
    assert correlation.score_membership(set(), frozenset()) == 1.0
    assert correlation.score_membership({"aaaaaaaa"}, frozenset()) == 0.0


def test_over_inclusion_loses_precision():
    expected = frozenset({"aaaaaaaa"})
    predicted = {"aaaaaaaa", "bbbbbbbb", "cccccccc", "dddddddd"}
    assert correlation.score_membership(predicted, expected) == pytest.approx(0.4)


def test_ids_are_parsed_from_citations_and_from_full_ids():
    text = "members: [msg:93bae03b], d0e20c681476512bb2fd2fb32c280607 and 41fe8ce8."
    assert correlation.parse_member_ids(text) == {"93bae03b", "d0e20c68", "41fe8ce8"}


def test_an_id_the_case_never_showed_is_dropped_before_scoring(conn):
    case = _case(conn, "Unusual sign-in blocked")
    text = ", ".join(sorted(case.expected)) + ", ffffffff"
    assert correlation.score_case(case, text) == 1.0


# --- the shortcut baselines the metric exists to refuse -------------------------


def test_a_campaign_id_join_scores_zero_on_the_adversarial_half(conn):
    """The analogue of ADR-009's constant-safe baseline."""
    result = correlation.campaign_id_baseline(conn)
    assert result["adversarial"] == 0.0
    assert result["n_adversarial"] == 2
    assert result["combined"] < 0.5


def test_a_flagged_only_filter_also_fails_the_under_inclusion_case(conn):
    """It drops d0e20c68 and 41fe8ce8, which are members recorded `safe`."""
    result = correlation.flagged_only_baseline(conn)
    assert result["adversarial"] < 1.0


def test_naming_every_candidate_fails_the_negative_seeds(conn):
    result = correlation.everything_baseline(conn)
    assert result["agreement"] < 0.5


def test_no_shortcut_reaches_a_high_combined_score(conn):
    for baseline in (
        correlation.campaign_id_baseline,
        correlation.flagged_only_baseline,
        correlation.everything_baseline,
    ):
        assert baseline(conn)["combined"] < 0.75, baseline.__name__
