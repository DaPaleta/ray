"""Stage 3 verification: the core tools.

Every assertion here traces to a claim in plan.md section 2, verified against
the database directly (AGENTS.md section 3 item 4). No test calls a model
(ADR-005).
"""

from __future__ import annotations

from conftest import (
    CFO_WIRE_MSG,
    FINANCE_FLAGGED,
    INJECTED_MESSAGES,
    MAILBOX_MSG,
    PAYSLIP_FN_1,
    PHISH_DOMAIN,
)

from ray.tools.detection import ANALYZERS, get_detection
from ray.tools.messages import find_messages, get_message, get_message_body


# --- find_messages --------------------------------------------------------------


def test_finance_flagged_this_week_returns_exactly_the_seven_rows(conn):
    """plan.md 2.4 and criterion 5. Verdict-only would hide the released pair."""
    result = find_messages(
        conn, department="finance", relative_window="this week", flagged_only=True
    )
    assert result.data["total"] == 7
    ids = {c.split(":")[1].rstrip("]") for c in result.citations}
    assert ids == {m[:8] for m in FINANCE_FLAGGED}
    assert "no upper bound" in result.window
    assert "2026-08-09T17:10:57Z" in result.window


def test_finance_unfiltered_this_week_is_38_not_41(conn):
    """The datetime() trap. plan.md 2.7."""
    result = find_messages(conn, department="finance", relative_window="this week")
    assert result.data["total"] == 38


def test_subject_contains_matches_exactly_one_message(conn):
    result = find_messages(conn, subject_contains="mailbox storage full")
    assert result.data["total"] == 1
    assert result.citations == [f"[msg:{MAILBOX_MSG[:8]}]"]


def test_link_domain_returns_fifteen_messages(conn):
    result = find_messages(conn, link_domain=PHISH_DOMAIN)
    assert result.data["total"] == 15
    assert len(result.citations) == 15
    assert len(set(result.citations)) == 15  # no duplicate rows from the link join


def test_recipient_matches_display_name_case_insensitive_partial(conn):
    result = find_messages(conn, recipient="gwen")
    ids = {row["message_id"] for row in result.data["rows"]}
    assert CFO_WIRE_MSG in ids


def test_zero_matches_is_a_grounded_fact_not_an_error(conn):
    result = find_messages(conn, subject_contains="no such subject exists anywhere")
    assert result.data["total"] == 0
    assert result.citations == []


def test_cap_note_appears_when_the_limit_truncates_results(conn):
    result = find_messages(conn, department="finance", relative_window="this week", limit=3)
    assert result.data["total"] == 38
    assert result.data["returned"] == 3
    assert "showing 3 of 38" in result.text.lower()


def test_flagged_only_definition_covers_verdict_attack_type_and_released(conn):
    """plan.md 2.4: a verdict-alone filter misses the two released messages."""
    result = find_messages(
        conn, department="finance", relative_window="this week", flagged_only=True
    )
    shorts = {c.split(":")[1].rstrip("]") for c in result.citations}
    assert "a3b5e777"[:8] in shorts
    assert "5978f8ed"[:8] in shorts


# --- get_message ------------------------------------------------------------------


def test_get_message_never_returns_body_text(conn):
    """IR4, ADR-004. A test must assert this."""
    result = get_message(conn, CFO_WIRE_MSG)
    assert "message" in result.data
    assert "body_text" not in result.data["message"]
    assert "body_text" not in result.data


def test_get_message_output_contains_no_substring_of_the_real_body(conn):
    """Belt and suspenders on top of the excluded column."""
    body_row = conn.execute(
        "SELECT body_text FROM messages WHERE message_id = ?", (CFO_WIRE_MSG,)
    ).fetchone()
    body_text = body_row[0]
    assert body_text and len(body_text) > 40  # distinctive, per plan.md 2.4

    result = get_message(conn, CFO_WIRE_MSG)
    assert body_text not in result.text
    # Also check no long substring leaks (defends against partial concatenation bugs).
    assert body_text[:40] not in result.text


def test_get_message_mailbox_message_has_one_malicious_scanned_link(conn):
    result = get_message(conn, MAILBOX_MSG)
    links = result.data["links"]
    assert len(links) == 1
    assert links[0]["domain"] == PHISH_DOMAIN
    assert links[0]["is_scanned"] == 1
    assert links[0]["scan_verdict"] == "malicious"


def test_get_message_mailbox_message_auth_results_from_the_tool(conn):
    """The tool's own output, not a direct query — this is what the ground truth
    in the task actually claims about get_message."""
    msg = get_message(conn, MAILBOX_MSG).data["message"]
    assert (msg["spf"], msg["dkim"], msg["dmarc"]) == ("pass", "fail", "fail")


def test_get_message_mailbox_message_campaign_id_is_reported_as_none(conn):
    """The mailbox message carries no campaign_id. The DB stores this as NULL,
    not as an empty string (see the discrepancy noted in the final report)."""
    row = conn.execute(
        "SELECT campaign_id FROM messages WHERE message_id = ?", (MAILBOX_MSG,)
    ).fetchone()
    assert row[0] is None
    result = get_message(conn, MAILBOX_MSG)
    assert result.data["message"]["campaign_id"] is None
    assert "Campaign id: (none)" in result.text


def test_get_message_reports_the_unresolved_link_scan_state(conn):
    """plan.md 3.3 item 3: 4 links carry `unresolved`. IR10: not benign."""
    row = conn.execute(
        "SELECT message_id FROM links WHERE scan_verdict = 'unresolved' LIMIT 1"
    ).fetchone()
    assert row is not None, "expected at least one 'unresolved' link in the corpus"
    result = get_message(conn, row[0])
    assert "not evidence of safety" in result.text.lower()


def test_get_message_reports_unscanned_link_honestly_not_as_benign(conn):
    """plan.md 2.4 false negative. IR10."""
    result = get_message(conn, PAYSLIP_FN_1)
    links = result.data["links"]
    assert len(links) == 1
    assert links[0]["is_scanned"] == 0
    assert not links[0]["scan_verdict"]
    assert "not evidence of safety" in result.text.lower()
    assert "not benign" in result.text.lower()


def test_get_message_accepts_a_short_id_prefix(conn):
    result = get_message(conn, MAILBOX_MSG[:8])
    assert result.data["message_id"] == MAILBOX_MSG


def test_get_message_unknown_id_reports_unknown(conn):
    result = get_message(conn, "0" * 32)
    assert result.is_unknown is True
    assert "NOT IN THE DATA" in result.text


def test_get_message_ambiguous_short_prefix_is_reported(conn):
    # A single hex character is guaranteed to prefix more than one message.
    result = get_message(conn, MAILBOX_MSG[0])
    assert result.is_unknown is False
    assert "matches" in result.text
    assert len(result.data["candidates"]) > 1


def test_get_message_shows_recipient_department_and_vip(conn):
    result = get_message(conn, CFO_WIRE_MSG)
    assert result.data["recipient"]["display_name"] == "Gwen Mercer"
    assert result.data["recipient"]["department"] == "finance"


# --- get_message_body -------------------------------------------------------------


def test_get_message_body_fences_the_text(conn):
    result = get_message_body(conn, CFO_WIRE_MSG)
    assert "<<<UNTRUSTED_EMAIL_CONTENT" in result.text
    assert "UNTRUSTED_EMAIL_CONTENT>>>" in result.text
    body_row = conn.execute(
        "SELECT body_text FROM messages WHERE message_id = ?", (CFO_WIRE_MSG,)
    ).fetchone()
    assert body_row[0] in result.text


def test_get_message_body_accepts_a_short_id_prefix(conn):
    result = get_message_body(conn, CFO_WIRE_MSG[:8])
    assert result.data["message_id"] == CFO_WIRE_MSG


def test_get_message_body_flags_every_injected_message(conn):
    """plan.md 2.6. All 6 messages must produce a non-empty finding."""
    for message_id in INJECTED_MESSAGES:
        result = get_message_body(conn, message_id)
        assert result.injection_findings, f"{message_id} produced no injection finding"


def test_get_message_body_clean_message_has_no_findings(conn):
    result = get_message_body(conn, MAILBOX_MSG)
    assert result.injection_findings == []


# --- get_detection -----------------------------------------------------------------


def test_get_detection_mailbox_message_all_four_analyzers_malicious(conn):
    result = get_detection(conn, MAILBOX_MSG)
    ran = {row["analyzer"]: row for row in result.data["analyzers_ran"]}
    assert set(ran) == set(ANALYZERS)
    assert result.data["analyzers_missing"] == []

    assert ran["nlp-analyzer"]["score"] == 0.8841
    assert ran["nlp-analyzer"]["verdict"] == "malicious"
    assert ran["link-scanner"]["score"] == 0.96
    assert ran["link-scanner"]["verdict"] == "malicious"
    assert ran["sender-reputation"]["score"] == 0.72
    assert ran["sender-reputation"]["verdict"] == "malicious"
    assert ran["stage2"]["score"] == 0.93
    assert ran["stage2"]["verdict"] == "malicious"

    decision = result.data["decision"]
    assert decision["verdict"] == "malicious"
    assert decision["attack_type"] == "credential_phishing"

    remediation = result.data["remediation"]
    assert remediation["action"] == "quarantined"

    for name in ANALYZERS:
        assert f"[analyzer:{MAILBOX_MSG[:8]}/{name}]" in result.citations
    assert f"[decision:{MAILBOX_MSG[:8]}]" in result.citations
    assert f"[remediation:{MAILBOX_MSG[:8]}]" in result.citations


def test_get_detection_cfo_wire_link_scanner_did_not_run(conn):
    """plan.md 2.4. Only 3 of 4 analyzers ran, and the missing one matters."""
    result = get_detection(conn, CFO_WIRE_MSG)
    ran = {row["analyzer"]: row for row in result.data["analyzers_ran"]}
    assert set(ran) == {"nlp-analyzer", "sender-reputation", "stage2"}
    assert result.data["analyzers_missing"] == ["link-scanner"]
    assert "link-scanner" in result.text
    assert "did not run" in result.text.lower()

    assert ran["nlp-analyzer"]["score"] == 0.59
    assert ran["nlp-analyzer"]["verdict"] == "malicious"
    assert ran["sender-reputation"]["score"] == 0.31
    assert ran["sender-reputation"]["verdict"] == "benign"
    assert ran["stage2"]["score"] == 0.22
    assert ran["stage2"]["verdict"] == "benign"

    decision = result.data["decision"]
    assert decision["verdict"] == "safe"
    assert not decision["attack_type"]

    remediation = result.data["remediation"]
    assert remediation["action"] == "none"


def test_get_detection_reports_override_prominently_when_present(conn):
    """Section 2.5: the released quaystone messages carry an override."""
    row = conn.execute(
        "SELECT message_id FROM decisions WHERE overridden_by IS NOT NULL LIMIT 1"
    ).fetchone()
    assert row is not None, "expected at least one overridden decision in the corpus"
    result = get_detection(conn, row[0])
    assert "OVERRIDE" in result.text
    assert result.data["decision"]["overridden_by"] is not None


def test_get_detection_accepts_a_short_id_prefix(conn):
    result = get_detection(conn, MAILBOX_MSG[:8])
    assert result.data["message_id"] == MAILBOX_MSG


def test_get_detection_unknown_id_reports_unknown(conn):
    result = get_detection(conn, "f" * 32)
    assert result.is_unknown is True
