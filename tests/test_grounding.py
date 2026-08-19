"""Stage 5 verification: grounding turns "every claim traces to a row" into a
checked property, per plan.md section 4.6 and acceptance criterion 2.

No test here calls a model (ADR-005).
"""

from __future__ import annotations

from conftest import CFO_WIRE_MSG, MAILBOX_MSG

from ray import grounding
from ray.schemas import cite


# --- extract_citations ----------------------------------------------------------


def test_extract_citations_finds_every_kind():
    text = (
        "The message [msg:93bae03b] was quarantined per [decision:276266c0] and "
        "[analyzer:93bae03b/stage2] agreed. See [link:93bae03b], "
        "[remediation:93bae03b], and [user:u_cfo]."
    )
    parsed = grounding.extract_citations(text)
    kinds = [p[1] for p in parsed]
    assert kinds == ["msg", "decision", "analyzer", "link", "remediation", "user"]

    analyzer_entry = next(p for p in parsed if p[1] == "analyzer")
    assert analyzer_entry[2] == "93bae03b"  # identifier
    assert analyzer_entry[3] == "stage2"  # detail


def test_extract_citations_on_empty_string_and_garbage_does_not_raise():
    assert grounding.extract_citations("") == []
    assert grounding.extract_citations("[[[msg:") == []
    assert grounding.extract_citations("no citations here at all") == []


# --- verify: one real citation per kind -----------------------------------------


def test_msg_citation_passes(conn):
    report = grounding.verify(conn, cite("msg", MAILBOX_MSG))
    assert report.ok is True
    assert report.citation_count == 1


def test_decision_citation_passes(conn):
    report = grounding.verify(conn, cite("decision", CFO_WIRE_MSG))
    assert report.ok is True


def test_analyzer_citation_with_detail_passes(conn):
    report = grounding.verify(conn, cite("analyzer", MAILBOX_MSG, "stage2"))
    assert report.ok is True


def test_link_citation_passes(conn):
    report = grounding.verify(conn, cite("link", MAILBOX_MSG))
    assert report.ok is True


def test_remediation_citation_passes(conn):
    report = grounding.verify(conn, cite("remediation", MAILBOX_MSG))
    assert report.ok is True


def test_user_citation_passes(conn):
    report = grounding.verify(conn, "[user:u_cfo]")
    assert report.ok is True


# --- fabrication and coverage traps ---------------------------------------------


def test_fabricated_message_id_fails(conn):
    report = grounding.verify(conn, "[msg:deadbeef]")
    assert report.ok is False
    assert report.failures[0].raw == "[msg:deadbeef]"


def test_analyzer_that_never_ran_on_the_message_fails(conn):
    """The flagship test. link-scanner did not run on the CFO wire message —

    only nlp-analyzer, sender-reputation, and stage2 did (plan.md 2.4, 4.6).
    A citation that names a real message but the wrong analyzer must fail.
    """
    bad = grounding.verify(conn, cite("analyzer", CFO_WIRE_MSG, "link-scanner"))
    assert bad.ok is False
    assert bad.failures[0].kind == "analyzer"
    assert bad.failures[0].detail == "link-scanner"

    good = grounding.verify(conn, cite("analyzer", CFO_WIRE_MSG, "stage2"))
    assert good.ok is True


def test_sender_reputation_ran_on_the_mailbox_message(conn):
    """sender-reputation ran on only 2 messages in the whole corpus; this is one."""
    report = grounding.verify(conn, cite("analyzer", MAILBOX_MSG, "sender-reputation"))
    assert report.ok is True


def test_unknown_citation_kind_is_a_failure_not_an_exception(conn):
    report = grounding.verify(conn, "[mystery:abc]")
    assert report.ok is False
    assert report.failures[0].kind == "mystery"
    assert report.failures[0].problem is not None


def test_mem_citation_fails_while_agent_memory_is_empty(conn):
    """agent_memory is empty until stage 6 writes a row (plan.md 2.1)."""
    report = grounding.verify(conn, "[mem:anything]")
    assert report.ok is False


# --- mixed report -----------------------------------------------------------------


def test_sql_wildcard_identifiers_do_not_forge_a_pass(conn):
    """The identifier comes from the answer under verification, i.e. from the

    model. A naive `LIKE identifier || '%'` treats `_` and `%` as wildcards, so
    `[msg:________]` (8 underscores) would match any 32-char message_id, and
    `[msg:%]` would match every row. Neither may verify as real.
    """
    assert grounding.verify(conn, "[msg:________]").ok is False
    assert grounding.verify(conn, "[msg:%]").ok is False
    assert grounding.verify(conn, "[user:u%]").ok is False


def test_mixed_good_and_bad_report(conn):
    text = f"{cite('msg', MAILBOX_MSG)} but also [msg:deadbeef] and [mystery:x]"
    report = grounding.verify(conn, text)
    assert report.ok is False
    assert report.citation_count == 3
    failure_raws = {c.raw for c in report.failures}
    assert failure_raws == {"[msg:deadbeef]", "[mystery:x]"}
    assert "FAILED" in report.summary()


def test_all_good_report_summary(conn):
    report = grounding.verify(conn, cite("msg", MAILBOX_MSG))
    assert "verified" in report.summary()


# --- no citations at all -----------------------------------------------------------


def test_no_citations_has_zero_count(conn):
    report = grounding.verify(conn, "This message looks suspicious.")
    assert report.citation_count == 0
    assert report.ok is True  # vacuously true; nothing failed
    assert "No citations" in report.summary()


def test_warn_if_uncited_flags_a_claim_shaped_sentence():
    warning = grounding.warn_if_uncited(
        "The message is malicious and was quarantined by the system."
    )
    assert warning is not None
    assert "citation" in warning.lower()


def test_warn_if_uncited_is_silent_when_cited():
    text = f"The message is malicious {cite('msg', MAILBOX_MSG)}."
    assert grounding.warn_if_uncited(text) is None


def test_warn_if_uncited_is_silent_on_empty_text():
    assert grounding.warn_if_uncited("") is None
    assert grounding.warn_if_uncited("   ") is None


# --- never raises on malformed input --------------------------------------------


def test_verify_on_empty_string_does_not_raise(conn):
    report = grounding.verify(conn, "")
    assert report.citation_count == 0
    assert report.ok is True


def test_verify_on_garbage_does_not_raise(conn):
    report = grounding.verify(conn, "[[[msg:")
    assert report.citation_count == 0
    assert report.ok is True


def test_verify_uses_the_shared_citation_kind_map(conn):
    """grounding.py must key off schemas.CITATION_KINDS, not a private copy.

    Proof: every kind schemas.py knows about verifies against the table and
    column that CITATION_KINDS names, using a real row from that exact table.
    """
    from ray.schemas import CITATION_KINDS

    row_for_kind = {
        "msg": cite("msg", MAILBOX_MSG),
        "decision": cite("decision", MAILBOX_MSG),
        "analyzer": cite("analyzer", MAILBOX_MSG, "stage2"),
        "link": cite("link", MAILBOX_MSG),
        "remediation": cite("remediation", MAILBOX_MSG),
        "user": "[user:u_cfo]",
    }
    for kind in CITATION_KINDS:
        if kind == "mem":
            continue  # agent_memory is empty; covered separately
        report = grounding.verify(conn, row_for_kind[kind])
        assert report.ok, f"{kind} citation unexpectedly failed: {report.failures}"


# --- tool names dressed as citations (ADR-011 follow-up) ------------------------


def test_a_tool_name_in_brackets_is_reported(conn):
    """`[blast_radius]` looks like a citation and is not one. A live run produced it."""
    found = grounding.find_pseudo_citations(
        "The baseline supports quarantine [blast_radius] for both [msg:d0e20c68]."
    )
    assert found == ["[blast_radius]"]


def test_pseudo_citations_are_deduplicated_and_ordered():
    text = "[domain_intel] then [find_messages] then [domain_intel] again"
    assert grounding.find_pseudo_citations(text) == ["[domain_intel]", "[find_messages]"]


def test_a_real_citation_is_never_a_pseudo_citation():
    for raw in ("[msg:93bae03b]", "[analyzer:93bae03b/stage2]", "[user:u_cfo]"):
        assert grounding.find_pseudo_citations(raw) == []


def test_the_mirrored_tool_names_match_the_built_registry(conn):
    """A new tool must not slip past the detector (grounding.TOOL_NAMES)."""
    from ray import config as config_module
    from ray import subagents

    ctx = subagents.RayContext(cfg=config_module.load_config(env={}), conn=conn)
    assert set(grounding.TOOL_NAMES) == set(subagents.build_tools(ctx))
