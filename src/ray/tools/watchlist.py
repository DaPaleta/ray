"""The watchlist sweep. Capability 5b, plan.md section 4.5, ADR-010.

`watchlist_sweep` applies every stored `watch` memory record across the corpus
and reports what matches. It reads `agent_memory` directly with `db.rows` — it
does not import from `memory.py`'s proposal machinery, because a sweep only
reads what the analyst has already confirmed. It never writes anything.

ADR-010 is explicit that nothing appends to this database: a sweep is a pull
over stored rows, and it never reports a match as newly arriving or as
happening in real time (IR9).

`extract_indicators` is a small, pragmatic extractor: a watch record's content
is an analyst sentence, such as "Watch quaystone-billing-portal.com: five
messages were released on one phone confirmation." It pulls out domains, email
addresses, and quoted strings as candidate indicators. It favours being
well-tested over being clever.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .. import db, schemas
from . import intel
from .exposure import _messages_for_domain

WATCH_KIND = "watch"

# A reasonably strict email shape: local part, '@', a domain with a real TLD.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# A hostname-shaped token: two or more dot-separated labels, each alphanumeric
# with optional internal hyphens. Word-bounded so trailing punctuation such as
# ':' or a sentence-ending '.' with nothing after it is never swept in.
_DOMAIN_RE = re.compile(
    r"\b[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+\b"
)

# Double-quoted spans only. Single quotes are also apostrophes in ordinary
# analyst prose ("don't", "vendor's"), and an apostrophe-delimited "quote" would
# pull ordinary words in as false candidate indicators.
_QUOTED_RE = re.compile(r'"([^"]+)"')

# Domains this short or generic are never useful watch candidates on their own,
# e.g. an accidental match inside a version number or a stray "e.g." Kept out of
# extraction results so a sweep does not spend time on noise.
_MIN_DOMAIN_LEN = 4


def extract_indicators(text: str) -> list[str]:
    """Pull candidate indicators — domains, emails, quoted strings — out of an
    analyst sentence. Order-preserving, case-insensitive de-duplication.
    """
    text = text or ""
    found: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        candidate = value.strip().strip(".,;:!?\"'()[]{}")
        if not candidate:
            return
        key = candidate.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(candidate)

    for match in _EMAIL_RE.finditer(text):
        add(match.group(0))

    # Strip emails before scanning for bare domains, so the domain half of an
    # email is not also reported as a separate, redundant candidate.
    without_emails = _EMAIL_RE.sub(" ", text)
    for match in _DOMAIN_RE.finditer(without_emails):
        candidate = match.group(0)
        if len(candidate) >= _MIN_DOMAIN_LEN:
            add(candidate)

    for match in _QUOTED_RE.finditer(text):
        quoted = match.group(1)
        if quoted:
            add(quoted)

    return found


def _looks_like_domain(candidate: str) -> bool:
    return "@" not in candidate and bool(intel._DOMAIN_SHAPE_RE.match(candidate))


def _match_indicator(conn: sqlite3.Connection, candidate: str) -> set[str]:
    """Message ids this candidate indicator reaches, or an empty set."""
    text = candidate.strip()
    if not text:
        return set()
    if "@" in text and _EMAIL_RE.fullmatch(text):
        rows = db.rows(
            conn,
            "SELECT message_id FROM messages WHERE LOWER(sender_email) = ?",
            (text.lower(),),
        )
        return {r["message_id"] for r in rows}
    if _looks_like_domain(text):
        link_ids, sender_ids = _messages_for_domain(conn, text.lower())
        return link_ids | sender_ids
    return set()


def watchlist_sweep(conn: sqlite3.Connection, limit: int = 100) -> schemas.ToolResult:
    """Apply every stored `watch` record across the corpus and report matches.

    An empty watchlist is a real result (`is_unknown=True`), not an error. A
    watchlist with no matching message is also a real result, just not unknown.
    Nothing here simulates arrival: every reported row already sits in the
    database (IR9, ADR-010).
    """
    records = db.rows(
        conn,
        f"SELECT memory_id, kind, content, created_at FROM {db.MEMORY_TABLE} "
        "WHERE kind = ? ORDER BY created_at",
        (WATCH_KIND,),
    )
    if not records:
        return schemas.ToolResult(
            text=schemas.unknown(
                "watchlist sweep",
                "No watch record is stored yet in agent_memory. Ray applies no "
                "watch until the analyst proposes and confirms one (ADR-010).",
            ),
            is_unknown=True,
            data={"watch_record_count": 0, "matches": []},
        )

    record_candidates: dict[str, list[str]] = {}
    match_sources: dict[str, set[str]] = {}
    for rec in records:
        candidates = extract_indicators(rec["content"])
        record_candidates[rec["memory_id"]] = candidates
        for candidate in candidates:
            for mid in _match_indicator(conn, candidate):
                match_sources.setdefault(mid, set()).add(rec["memory_id"])

    citations = [schemas.cite("mem", r["memory_id"]) for r in records]

    if not match_sources:
        lines = [
            f"Watchlist sweep across {len(records)} stored watch record(s): "
            "no message in the corpus currently matches any stored indicator."
        ]
        for rec in records:
            checked = ", ".join(record_candidates[rec["memory_id"]]) or "(no indicator extracted)"
            lines.append(f"  {schemas.cite('mem', rec['memory_id'])} — checked: {checked}")
        return schemas.ToolResult(
            text="\n".join(lines),
            data={"watch_record_count": len(records), "matches": []},
            citations=citations,
        )

    message_ids = list(match_sources.keys())
    placeholders = ",".join("?" * len(message_ids))
    detail_rows = db.rows(
        conn,
        f"""
        SELECT m.message_id, m.received_at, m.sender_email, m.subject,
               d.verdict, d.attack_type, r.action
        FROM messages m
        LEFT JOIN decisions d ON d.message_id = m.message_id
        LEFT JOIN remediations r ON r.message_id = m.message_id
        WHERE m.message_id IN ({placeholders})
        ORDER BY m.received_at
        """,
        tuple(message_ids),
    )

    total = len(detail_rows)
    limit = max(1, int(limit))
    capped = total > limit
    shown_rows = detail_rows[:limit]

    body = []
    matches_data: list[dict[str, Any]] = []
    for r in shown_rows:
        mid = r["message_id"]
        watch_ids = sorted(match_sources.get(mid, ()))
        watch_cites = ", ".join(schemas.cite("mem", w) for w in watch_ids)
        body.append(
            [
                schemas.short(mid),
                r["sender_email"],
                r["verdict"],
                r["attack_type"] or "",
                r["action"] if r["action"] is not None else "(none recorded)",
                schemas.inbox_state(r["action"]),
                watch_cites,
            ]
        )
        citations.append(schemas.cite("msg", mid))
        citations.append(schemas.cite("decision", mid))
        if r["action"] is not None:
            citations.append(schemas.cite("remediation", mid))
        matches_data.append(
            {
                "message_id": mid,
                "verdict": r["verdict"],
                "attack_type": r["attack_type"],
                "action": r["action"],
                "in_inbox": schemas.is_in_inbox(r["action"]),
                "watch_memory_ids": watch_ids,
            }
        )

    cap_note = f"... capped at {limit} of {total} matching messages" if capped else None
    lines = [
        f"Watchlist sweep across {len(records)} stored watch record(s): "
        f"{total} message(s) matched a stored indicator. This is a pull over stored "
        "rows, not a live feed — nothing here just arrived (IR9, ADR-010).",
        schemas.table(
            ["id", "sender", "verdict", "attack_type", "action", "inbox_state", "caught_by"],
            body,
            cap_note=cap_note,
        ),
    ]

    return schemas.ToolResult(
        text="\n".join(lines),
        data={
            "watch_record_count": len(records),
            "match_count": total,
            "matches": matches_data,
            "capped": capped,
        },
        citations=citations,
    )
