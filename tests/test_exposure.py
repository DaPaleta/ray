"""Tests for capability 5a: blast_radius.

Every number here is a known row from plan.md section 2, verified against the
database (plan.md section 9 item 2 and item 5, AGENTS.md section 3 item 4). No
test calls a model (ADR-005).
"""

from __future__ import annotations

from conftest import (
    ACME_PORTAL_CAMPAIGN,
    MAILBOX_MSG,
    PAYSLIP_FN_1,
    PAYSLIP_FN_2,
    PHISH_DOMAIN,
    QUAYSTONE_SENDER,
)

from ray import schemas
from ray.tools import exposure

QUAYSTONE_DOMAIN = QUAYSTONE_SENDER.split("@", 1)[1]


# ---------------------------------------------------------------------------
# login-verify.acme-portal.co — 15 messages, 7 departments, 1 VIP, 13/2 split
# ---------------------------------------------------------------------------


def test_acme_portal_message_and_recipient_counts(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert not result.is_unknown
    assert result.data["message_count"] == 15
    assert result.data["recipient_count"] == 15
    assert result.data["department_count"] == 7


def test_acme_portal_vip_hit_is_talia_moreau(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert result.data["vip_hit_count"] == 1
    assert "Talia Moreau" in result.text
    assert "exec" in result.text


def test_acme_portal_remediation_split(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert result.data["quarantined_count"] == 13
    assert set(result.data["live_message_ids"]) == {PAYSLIP_FN_1, PAYSLIP_FN_2}


def test_acme_portal_recommendation_names_the_two_live_messages(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert "RECOMMENDATION" in result.text
    assert "quarantine" in result.text.lower()
    assert schemas.short(PAYSLIP_FN_1) in result.text
    assert schemas.short(PAYSLIP_FN_2) in result.text
    # Ray recommends; Ray never claims to have acted.
    assert "cannot quarantine or release" in result.text


def test_acme_portal_citations_present(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert any(c.startswith("[msg:") for c in result.citations)
    assert any(c.startswith("[decision:") for c in result.citations)
    assert any(c.startswith("[remediation:") for c in result.citations)


# ---------------------------------------------------------------------------
# quaystone-billing-portal.com — 5 released messages, all overridden
# ---------------------------------------------------------------------------


def test_quaystone_all_five_released_and_live(conn):
    result = exposure.blast_radius(conn, QUAYSTONE_DOMAIN)
    assert not result.is_unknown
    assert result.data["message_count"] == 5
    assert result.data["quarantined_count"] == 0
    assert len(result.data["live_message_ids"]) == 5


def test_quaystone_department_breakdown(conn):
    result = exposure.blast_radius(conn, QUAYSTONE_DOMAIN)
    breakdown = result.data["department_breakdown"]
    assert breakdown == {"operations": 1, "sales": 2, "finance": 2}


def test_quaystone_override_reasons_all_present(conn):
    result = exposure.blast_radius(conn, QUAYSTONE_DOMAIN)
    assert "tunde.okafor@acme.com" in result.text
    assert "Assuming same as the others." in result.text
    assert "Vendor confirmed by phone, legitimate billing portal migration." in result.text
    assert len(result.data["overridden_message_ids"]) == 5


def test_quaystone_every_row_holds_the_same_recorded_facts(conn):
    """Ground truth: all 5 keep verdict=safe, attack_type=credential_phishing, and
    the same overriding analyst, even though the recorded verdict is 'safe'.
    """
    result = exposure.blast_radius(conn, QUAYSTONE_DOMAIN)
    for row in result.data["messages"]:
        assert row["action"] == "released"
        assert row["verdict"] == "safe"
        assert row["attack_type"] == "credential_phishing"
        assert row["overridden_by"] == "tunde.okafor@acme.com"


def test_quaystone_no_false_quarantine_recommendation(conn):
    """No sibling on this indicator was quarantined, so Ray must not invent one."""
    result = exposure.blast_radius(conn, QUAYSTONE_DOMAIN)
    assert "no remediation baseline" in result.text or "cannot quarantine or release" in result.text
    assert "cannot quarantine or release" in result.text


# ---------------------------------------------------------------------------
# acme-robotics.com — a single message, Gwen Mercer, finance, action none
# ---------------------------------------------------------------------------


def test_acme_robotics_single_message(conn):
    result = exposure.blast_radius(conn, "acme-robotics.com")
    assert not result.is_unknown
    assert result.data["message_count"] == 1
    row = result.data["messages"][0]
    assert row["display_name"] == "Gwen Mercer"
    assert row["department"] == "finance"
    assert row["action"] == "none"
    assert "276266c0" in result.text


def test_acme_robotics_message_is_live(conn):
    result = exposure.blast_radius(conn, "acme-robotics.com")
    assert result.data["live_message_ids"] == ["276266c04c4256d0ad5b1f4f1294a2d6"]


# ---------------------------------------------------------------------------
# Resolution across every indicator kind blast_radius accepts
# ---------------------------------------------------------------------------


def test_campaign_id_resolution_is_narrower_than_the_domain(conn):
    """Query trap 1: a campaign_id join returns 14, one fewer than the 15 the
    shared-indicator domain resolves to, because message 93bae03b carries no
    campaign_id. blast_radius must report exactly what the resolved kind means,
    not silently widen a campaign query into a domain query.
    """
    result = exposure.blast_radius(conn, ACME_PORTAL_CAMPAIGN)
    assert not result.is_unknown
    assert result.data["resolved_kind"] == "campaign"
    assert result.data["message_count"] == 14
    assert MAILBOX_MSG not in {m["message_id"] for m in result.data["messages"]}


def test_sender_email_resolution_matches_the_domain_result(conn):
    result = exposure.blast_radius(conn, QUAYSTONE_SENDER)
    assert result.data["resolved_kind"] == "sender"
    assert result.data["message_count"] == 5


def test_message_id_resolution_is_exactly_one_message(conn):
    result = exposure.blast_radius(conn, MAILBOX_MSG)
    assert result.data["resolved_kind"] == "message"
    assert result.data["message_count"] == 1
    assert result.data["messages"][0]["message_id"] == MAILBOX_MSG


# ---------------------------------------------------------------------------
# limit and cap
# ---------------------------------------------------------------------------


def test_limit_caps_the_displayed_table_but_not_the_counted_totals(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN, limit=5)
    assert result.data["capped"] is True
    assert result.data["message_count"] == 15  # totals still reflect all 15
    assert "capped at 5 of 15" in result.text


# ---------------------------------------------------------------------------
# Resolution and edge cases
# ---------------------------------------------------------------------------


def test_unresolvable_indicator_is_unknown(conn):
    result = exposure.blast_radius(conn, "totally-unresolvable-indicator-xyz")
    assert result.is_unknown
    assert "NOT IN THE DATA" in result.text


def test_blast_radius_states_never_acts(conn):
    result = exposure.blast_radius(conn, PHISH_DOMAIN)
    assert "recommend" in result.text.lower()
    assert "cannot quarantine or release" in result.text
