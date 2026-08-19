"""Tests for the stage-4 intel tools: domain_intel, entity_graph, find_users.

Every number asserted here is a known row from plan.md section 2, run against
the database, per plan.md section 9 item 2 and item 5. No test calls a model
(ADR-005).
"""

from __future__ import annotations

from conftest import MAILBOX_MSG, PAYSLIP_FN_1, PAYSLIP_FN_2, PHISH_DOMAIN, QUAYSTONE_SENDER

from ray.tools import intel, people

QUAYSTONE_DOMAIN = QUAYSTONE_SENDER.split("@", 1)[1]


# ---------------------------------------------------------------------------
# domain_intel
# ---------------------------------------------------------------------------


def test_domain_intel_acme_portal_link_counts(conn):
    result = intel.domain_intel(conn, PHISH_DOMAIN)
    assert not result.is_unknown
    assert result.data["link_row_count"] == 15
    assert result.data["message_count"] == 15


def test_domain_intel_acme_portal_verdict_split(conn):
    result = intel.domain_intel(conn, PHISH_DOMAIN)
    assert "scan_verdict=malicious: 13" in result.text
    assert "is_scanned=0" in result.text
    for mid in (PAYSLIP_FN_1, PAYSLIP_FN_2):
        assert mid[:8] in result.text


def test_domain_intel_acme_portal_recipients_and_vip(conn):
    result = intel.domain_intel(conn, PHISH_DOMAIN)
    assert "7 departments" in result.text
    assert "VIP recipients hit: 1" in result.text
    assert "Talia Moreau" in result.text
    assert "exec" in result.text


def test_domain_intel_acme_portal_campaign_coverage(conn):
    result = intel.domain_intel(conn, PHISH_DOMAIN)
    assert "cmp_acme_portal_2026_07: 14 of 15" in result.text


def test_domain_intel_acme_portal_citations_present(conn):
    result = intel.domain_intel(conn, PHISH_DOMAIN)
    assert len(result.citations) > 0
    assert any(c.startswith("[link:") for c in result.citations)


def test_domain_intel_lookalike_flags_acme_robotics(conn):
    result = intel.domain_intel(conn, "acme-robotics.com")
    assert not result.is_unknown
    assert result.data["message_count"] == 1
    assert result.data["is_lookalike"] is True
    assert result.data["is_own_domain"] is False
    assert "LOOKALIKE WARNING" in result.text
    # the passing authentication must not read as reassurance
    assert "spf=pass dkim=pass dmarc=pass: 1" in result.text
    assert "not reassurance" in result.text


def test_domain_intel_quaystone_billing_portal_overrides(conn):
    result = intel.domain_intel(conn, QUAYSTONE_DOMAIN)
    assert not result.is_unknown
    assert result.data["message_count"] == 5
    assert "released: 5" in result.text
    assert "tunde.okafor@acme.com: 5" in result.text
    assert "safe/credential_phishing: 5" in result.text


def test_domain_intel_unknown_domain(conn):
    result = intel.domain_intel(conn, "no-such-domain-in-this-corpus.example")
    assert result.is_unknown
    assert "NOT IN THE DATA" in result.text


def test_domain_intel_is_case_and_dot_insensitive(conn):
    upper = intel.domain_intel(conn, " LOGIN-VERIFY.ACME-PORTAL.CO ")
    assert upper.data["message_count"] == 15


# ---------------------------------------------------------------------------
# entity_graph
# ---------------------------------------------------------------------------


def test_entity_graph_acme_portal_reaches_15_not_14(conn):
    result = intel.entity_graph(conn, PHISH_DOMAIN)
    message_nodes = [n for n in result.data["nodes"] if n["kind"] == "message"]
    assert len(message_nodes) == 15
    ids = {n["id"] for n in message_nodes}
    assert f"msg:{MAILBOX_MSG}" in ids


def test_entity_graph_subdomain_matching_reaches_same_15(conn):
    result = intel.entity_graph(conn, "acme-portal.co")
    message_nodes = [n for n in result.data["nodes"] if n["kind"] == "message"]
    assert len(message_nodes) == 15


def test_entity_graph_message_seed_depth1(conn):
    result = intel.entity_graph(conn, MAILBOX_MSG, depth=1)
    nodes = result.data["nodes"]
    kinds = {n["kind"] for n in nodes}
    assert "message" in kinds
    assert "user" in kinds
    assert "domain" in kinds
    domain_labels = {n["label"] for n in nodes if n["kind"] == "domain"}
    assert PHISH_DOMAIN in domain_labels
    # this message's campaign_id is empty, so no campaign node is expected
    assert "campaign" not in kinds


def test_entity_graph_message_seed_short_id_prefix(conn):
    result = intel.entity_graph(conn, MAILBOX_MSG[:8], depth=1)
    assert not result.is_unknown
    message_nodes = [n for n in result.data["nodes"] if n["kind"] == "message"]
    assert message_nodes[0]["id"] == f"msg:{MAILBOX_MSG}"


def test_entity_graph_message_seed_depth2_finds_campaign_siblings(conn):
    # The critical behaviour: joining through the shared link domain, not
    # campaign_id, must let a depth-2 walk from the orphaned message reach the
    # other 14 acme-portal messages.
    result = intel.entity_graph(conn, MAILBOX_MSG, depth=2, limit=60)
    message_nodes = [n for n in result.data["nodes"] if n["kind"] == "message"]
    assert len(message_nodes) == 15


def test_entity_graph_node_kinds_are_valid(conn):
    result = intel.entity_graph(conn, PHISH_DOMAIN, depth=2, limit=60)
    allowed = {"message", "user", "domain", "campaign", "sender"}
    for n in result.data["nodes"]:
        assert n["kind"] in allowed
        assert "id" in n and "label" in n
    for e in result.data["edges"]:
        assert {"source", "target", "relation"} <= e.keys()


def test_entity_graph_respects_limit_and_states_cap(conn):
    result = intel.entity_graph(conn, PHISH_DOMAIN, depth=2, limit=5)
    assert len(result.data["nodes"]) <= 5
    assert "cap" in result.text.lower()


def test_entity_graph_unknown_indicator(conn):
    result = intel.entity_graph(conn, "totally-unresolvable-indicator-xyz")
    assert result.is_unknown
    assert result.data["nodes"] == []
    assert result.data["edges"] == []


def test_entity_graph_data_is_json_serializable(conn):
    import json

    result = intel.entity_graph(conn, PHISH_DOMAIN)
    json.dumps(result.data)  # must not raise


# ---------------------------------------------------------------------------
# find_users
# ---------------------------------------------------------------------------


def test_find_users_department_finance(conn):
    result = people.find_users(conn, department="finance")
    assert not result.is_unknown
    assert result.data["match_count"] == 9
    assert all(u["department"] == "finance" for u in result.data["users"])


def test_find_users_vip_all_exec(conn):
    result = people.find_users(conn, is_vip=True)
    assert result.data["match_count"] == 9
    assert all(u["is_vip"] for u in result.data["users"])
    assert all(u["department"] == "exec" for u in result.data["users"])


def test_find_users_exact_single_name_match(conn):
    result = people.find_users(conn, name="Rachel Adler")
    assert result.data["match_count"] == 1
    user = result.data["users"][0]
    assert user["user_id"] == "u_cfo"
    assert user["email"] == "rachel.adler@acme.com"
    assert user["title"] == "Chief Financial Officer"


def test_find_users_ambiguous_name_returns_all_and_asks(conn):
    result = people.find_users(conn, name="Elena")
    assert result.data["match_count"] > 1
    assert "must choose" in result.text.lower()


def test_find_users_no_match_is_unknown(conn):
    result = people.find_users(conn, name="Nobody Has This Name At All")
    assert result.is_unknown


def test_find_users_citations(conn):
    result = people.find_users(conn, name="Rachel Adler")
    assert result.citations == ["[user:u_cfo]"]
