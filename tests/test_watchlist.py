"""Tests for capability 5b: watchlist_sweep and extract_indicators.

The committed database ships with an empty `agent_memory` table (ADR-010
follow-up), so any test that needs a `watch` record writes into a temporary
copy, exactly as `tests/test_memory.py` does. The committed database is never
touched. No test calls a model (ADR-005).
"""

from __future__ import annotations

import shutil

import pytest
from conftest import QUAYSTONE_SENDER

from ray import db
from ray.tools import watchlist

QUAYSTONE_DOMAIN = QUAYSTONE_SENDER.split("@", 1)[1]

WATCH_CONTENT = (
    "Watch quaystone-billing-portal.com: five messages were released on one phone "
    "confirmation, so a further message from that domain needs a fresh check."
)


@pytest.fixture()
def watch_db(tmp_path, cfg):
    """A throwaway copy of the database with one confirmed `watch` record."""
    target = tmp_path / "watch-copy.db"
    shutil.copy(cfg.db_path, target)

    write_conn = db.connect_memory(target)
    memory_id = "mem_test_watch_quaystone"
    try:
        write_conn.execute(
            "INSERT INTO agent_memory (memory_id, kind, content, created_at, source)"
            " VALUES (?, ?, ?, ?, ?)",
            (memory_id, "watch", WATCH_CONTENT, "2026-08-19T00:00:00Z", "analyst"),
        )
        write_conn.commit()
    finally:
        write_conn.close()

    read_conn = db.connect_readonly(target)
    yield read_conn, memory_id
    read_conn.close()


# ---------------------------------------------------------------------------
# extract_indicators
# ---------------------------------------------------------------------------


def test_extract_indicators_pulls_the_domain():
    result = watchlist.extract_indicators(WATCH_CONTENT)
    assert "quaystone-billing-portal.com" in result


def test_extract_indicators_no_trailing_punctuation():
    result = watchlist.extract_indicators(WATCH_CONTENT)
    for candidate in result:
        assert not candidate.endswith(":")
        assert not candidate.endswith(".")


def test_extract_indicators_ignores_ordinary_words():
    result = watchlist.extract_indicators(WATCH_CONTENT)
    for word in ("Watch", "five", "messages", "were", "released", "confirmation"):
        assert word not in result
        assert word.lower() not in [r.lower() for r in result]


def test_extract_indicators_pulls_an_email():
    result = watchlist.extract_indicators(
        "Watch billing@quaystone-billing-portal.com for any further contact."
    )
    assert "billing@quaystone-billing-portal.com" in result


def test_extract_indicators_pulls_a_quoted_string():
    result = watchlist.extract_indicators('The reason given was "Confirmed vendor."')
    assert any("Confirmed vendor" in r for r in result)


def test_extract_indicators_empty_text_returns_empty_list():
    assert watchlist.extract_indicators("") == []
    assert watchlist.extract_indicators(None) == []  # type: ignore[arg-type]


def test_extract_indicators_no_duplicate_domain_from_email():
    result = watchlist.extract_indicators("Watch billing@quaystone-billing-portal.com closely.")
    lowered = [r.lower() for r in result]
    assert lowered.count("quaystone-billing-portal.com") == 0  # only the full email is reported
    assert "billing@quaystone-billing-portal.com" in result


def test_extract_indicators_apostrophes_do_not_yield_ordinary_words():
    """A single quote is also an apostrophe in ordinary prose. It must not be read
    as a quoted-string delimiter, or "don't" and "vendor's" become false candidates.
    """
    result = watchlist.extract_indicators(
        "Don't trust the vendor's claim about quaystone-billing-portal.com."
    )
    lowered = [r.lower() for r in result]
    assert "t trust the vendor" not in lowered
    assert "quaystone-billing-portal.com" in lowered


# ---------------------------------------------------------------------------
# watchlist_sweep — empty watchlist is a real result
# ---------------------------------------------------------------------------


def test_sweep_with_empty_watchlist_is_unknown(conn):
    result = watchlist.watchlist_sweep(conn)
    assert result.is_unknown is True
    assert "NOT IN THE DATA" in result.text
    assert result.data["watch_record_count"] == 0


# ---------------------------------------------------------------------------
# watchlist_sweep — a confirmed watch on quaystone-billing-portal.com
# ---------------------------------------------------------------------------


QUAYSTONE_MESSAGE_IDS = {
    "c1e587141caa57faaa627f036324e876",
    "567beae60aa4532ba63cbad61e877af1",
    "a3b5e777c16358eba499a8e02e3caaa6",
    "5978f8ed9a4c53129adaeeb21db0a7ff",
    "0641802d9d225a48bf4a9fbe6623c13b",
}


def test_sweep_returns_the_five_quaystone_messages(watch_db):
    read_conn, memory_id = watch_db
    result = watchlist.watchlist_sweep(read_conn)
    assert result.is_unknown is False
    assert result.data["match_count"] == 5
    assert {m["message_id"] for m in result.data["matches"]} == QUAYSTONE_MESSAGE_IDS
    for m in result.data["matches"]:
        assert m["action"] == "released"
        assert m["in_inbox"] is True


def test_sweep_cites_the_watch_record(watch_db):
    read_conn, memory_id = watch_db
    result = watchlist.watchlist_sweep(read_conn)
    assert f"[mem:{memory_id[:8]}]" in result.citations
    for m in result.data["matches"]:
        assert memory_id in m["watch_memory_ids"]


def test_sweep_never_claims_a_live_arrival(watch_db):
    read_conn, _ = watch_db
    result = watchlist.watchlist_sweep(read_conn)
    assert "pull over stored rows" in result.text


def test_sweep_limit_caps_display_but_not_the_match_count(watch_db):
    read_conn, _ = watch_db
    result = watchlist.watchlist_sweep(read_conn, limit=2)
    assert result.data["capped"] is True
    assert result.data["match_count"] == 5  # totals still reflect all 5 matches
    assert "capped at 2 of 5" in result.text


def test_committed_database_agent_memory_stays_empty(conn):
    """The watch-insertion tests above must never touch the committed database."""
    assert db.scalar(conn, "SELECT COUNT(*) FROM agent_memory") == 0
