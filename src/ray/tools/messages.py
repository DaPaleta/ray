"""Message retrieval tools.

`find_messages` filters and lists. `get_message` returns one message's header
fields, authentication results, attachments, recipient, and links, but never
body text (IR4, ADR-004). `get_message_body` is the one path by which body text
enters the model's context, and it fences the text and scans it for injection
attempts (ADR-004 layer 2 and 3).

Every query lives here (IR2). Every row a tool returns carries a citation (IR1).
"""

from __future__ import annotations

import sqlite3

from .. import clock, db, injection, schemas

# The window resolved by find_messages joins on this column, per plan.md 2.7.
_RECEIVED_AT = "m.received_at"


def resolve_message_id(
    conn: sqlite3.Connection, message_id: str
) -> tuple[str | None, schemas.ToolResult | None]:
    """Resolve a full 32-char id or a short prefix to one full message id.

    Returns `(full_id, None)` on success, or `(None, error_result)` when the id
    matches nothing (is_unknown=True) or matches more than one message (an
    ambiguity report, not an "unknown" — the data has an answer, the id is not
    specific enough to pick it).
    """
    candidate = (message_id or "").strip()
    if not candidate:
        return None, schemas.ToolResult(
            text=schemas.unknown("a message id", "No message id was given."),
            is_unknown=True,
        )

    if len(candidate) >= 32:
        row = db.one(
            conn, "SELECT message_id FROM messages WHERE message_id = ?", (candidate,)
        )
        if row is None:
            return None, schemas.ToolResult(
                text=schemas.unknown(
                    f"message {candidate}", "No message with this id exists."
                ),
                is_unknown=True,
            )
        return str(row["message_id"]), None

    matches = db.rows(
        conn,
        "SELECT message_id FROM messages WHERE message_id LIKE ? ORDER BY message_id",
        (f"{candidate}%",),
    )
    if not matches:
        return None, schemas.ToolResult(
            text=schemas.unknown(
                f"message id prefix {candidate!r}",
                "No message id starts with this prefix.",
            ),
            is_unknown=True,
        )
    if len(matches) > 1:
        ids = [schemas.short(str(m["message_id"])) for m in matches]
        return None, schemas.ToolResult(
            text=(
                f"The id prefix {candidate!r} matches {len(matches)} messages: "
                f"{', '.join(ids)}. Give a longer prefix or the full id."
            ),
            data={"candidates": [str(m["message_id"]) for m in matches]},
        )
    return str(matches[0]["message_id"]), None


def _link_note(is_scanned: int | None, scan_verdict: str | None) -> str | None:
    """State a link's scan status honestly. IR10: unscanned is not benign."""
    verdict = (scan_verdict or "").strip().lower()
    if not is_scanned or verdict in ("", "unresolved"):
        return "NOT SCANNED or UNRESOLVED — this is not evidence of safety, only an absence of a scan result."
    return None


def find_messages(
    conn: sqlite3.Connection,
    *,
    department: str | None = None,
    recipient: str | None = None,
    sender_email: str | None = None,
    sender_domain: str | None = None,
    link_domain: str | None = None,
    subject_contains: str | None = None,
    verdict: str | None = None,
    attack_type: str | None = None,
    campaign_id: str | None = None,
    flagged_only: bool = False,
    relative_window: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 50,
) -> schemas.ToolResult:
    """Filter messages. Reports the resolved window, a total count, and a cap.

    `flagged_only=True` matches a non-safe verdict, OR a non-empty attack type,
    OR a `released` remediation (plan.md 2.4: a verdict filter alone hides the
    two released quaystone messages). `attack_type` and `campaign_id` may be
    stored as an empty string or as NULL when absent; this tool treats both the
    same way (IR2 trap 2).
    """
    window = clock.resolve_window(conn, relative_window, since, until)
    where_sql, params = window.clause(_RECEIVED_AT)

    joins = [
        "JOIN users u ON u.user_id = m.recipient_user_id",
        "JOIN decisions d ON d.message_id = m.message_id",
        "LEFT JOIN remediations r ON r.message_id = m.message_id",
    ]
    conditions = [where_sql]

    if department:
        conditions.append("LOWER(u.department) = LOWER(?)")
        params.append(department)
    if recipient:
        conditions.append("(LOWER(u.display_name) LIKE ? OR LOWER(u.email) LIKE ?)")
        pattern = f"%{recipient.lower()}%"
        params.extend([pattern, pattern])
    if sender_email:
        conditions.append("LOWER(m.sender_email) LIKE ?")
        params.append(f"%{sender_email.lower()}%")
    if sender_domain:
        conditions.append("LOWER(m.sender_email) LIKE ?")
        params.append(f"%@{sender_domain.lower()}")
    if link_domain:
        joins.append("JOIN links l ON l.message_id = m.message_id")
        conditions.append("LOWER(l.domain) = LOWER(?)")
        params.append(link_domain)
    if subject_contains:
        conditions.append("LOWER(m.subject) LIKE ?")
        params.append(f"%{subject_contains.lower()}%")
    if verdict:
        conditions.append("LOWER(d.verdict) = LOWER(?)")
        params.append(verdict)
    if attack_type:
        conditions.append("d.attack_type = ?")
        params.append(attack_type)
    if campaign_id:
        conditions.append("m.campaign_id = ?")
        params.append(campaign_id)
    if flagged_only:
        conditions.append(
            "(LOWER(d.verdict) != 'safe'"
            " OR (d.attack_type IS NOT NULL AND d.attack_type != '')"
            " OR LOWER(r.action) = 'released')"
        )

    where_all = " AND ".join(c for c in conditions if c)
    distinct = "DISTINCT " if link_domain else ""
    join_sql = " ".join(joins)

    total = db.scalar(
        conn,
        f"SELECT COUNT({distinct}m.message_id) FROM messages m {join_sql} WHERE {where_all}",
        params,
    )

    row_sql = (
        f"SELECT {distinct}m.message_id, m.received_at, m.sender_email, m.subject, "
        "u.display_name AS recipient_name, u.department, d.verdict, d.attack_type, "
        "r.action "
        f"FROM messages m {join_sql} WHERE {where_all} "
        "ORDER BY m.received_at DESC"
    )
    found = db.rows(conn, row_sql, params)
    capped = found[:limit]

    headers = [
        "id",
        "received_at",
        "sender_email",
        "subject",
        "recipient",
        "department",
        "verdict",
        "attack_type",
        "remediation",
    ]
    body_rows = [
        [
            schemas.short(row["message_id"]),
            row["received_at"],
            row["sender_email"],
            row["subject"],
            row["recipient_name"],
            row["department"],
            row["verdict"],
            row["attack_type"] or "(none)",
            schemas.inbox_state(row["action"]),
        ]
        for row in capped
    ]

    cap_note = None
    if total is not None and total > len(capped):
        cap_note = f"(showing {len(capped)} of {total} messages; increase limit to see more)"

    text = f"Found {total} message(s) matching the filters.\n\n" + schemas.table(
        headers, body_rows, cap_note=cap_note
    )

    citations = [schemas.cite("msg", row["message_id"]) for row in capped]

    return schemas.ToolResult(
        text=text,
        data={"total": total, "rows": found, "returned": len(capped)},
        citations=citations,
        window=window.description,
    )


def get_message(conn: sqlite3.Connection, message_id: str) -> schemas.ToolResult:
    """Header fields, authentication, attachments, recipient, and links.

    Never returns `body_text` (IR4, ADR-004). The SELECT list below excludes the
    column entirely, so no code path can leak it by accident.
    """
    resolved, error = resolve_message_id(conn, message_id)
    if error is not None:
        return error

    msg = db.one(
        conn,
        "SELECT message_id, received_at, sender_email, sender_display, "
        "recipient_user_id, subject, spf, dkim, dmarc, attachment_names, "
        "campaign_id FROM messages WHERE message_id = ?",
        (resolved,),
    )
    assert msg is not None  # resolve_message_id already confirmed existence

    user = db.one(
        conn,
        "SELECT user_id, display_name, department, is_vip FROM users WHERE user_id = ?",
        (msg["recipient_user_id"],),
    )
    links = db.rows(
        conn,
        "SELECT url, domain, is_scanned, scan_verdict FROM links WHERE message_id = ?",
        (resolved,),
    )

    short_id = schemas.short(resolved)
    campaign = msg["campaign_id"] or "(none)"
    attachments = msg["attachment_names"] or "(none)"

    if user is None:
        recipient_line = schemas.unknown(
            f"recipient for message {short_id}",
            f"No user row matches recipient_user_id {msg['recipient_user_id']!r}.",
        )
    else:
        vip = ", VIP" if user["is_vip"] else ""
        recipient_line = (
            f"{user['display_name']} ({user['department']}{vip}) "
            f"{schemas.cite('user', user['user_id'])}"
        )

    lines = [
        f"Message {short_id} {schemas.cite('msg', resolved)}",
        f"Subject: {msg['subject']}",
        f"Received: {msg['received_at']}",
        f"From: {msg['sender_display']} <{msg['sender_email']}>",
        f"To: {recipient_line}",
        f"Authentication — SPF: {msg['spf']}, DKIM: {msg['dkim']}, DMARC: {msg['dmarc']}",
        f"Attachments: {attachments}",
        f"Campaign id: {campaign}",
    ]

    link_headers = ["url", "domain", "is_scanned", "scan_verdict"]
    link_rows = [
        [link["url"], link["domain"], link["is_scanned"], link["scan_verdict"] or "(none)"]
        for link in links
    ]
    lines.append(f"\nLinks ({len(links)}):\n" + schemas.table(link_headers, link_rows))

    link_notes = [
        f"  - {link['domain']}: {_link_note(link['is_scanned'], link['scan_verdict'])}"
        for link in links
        if _link_note(link["is_scanned"], link["scan_verdict"])
    ]
    if link_notes:
        lines.append("\nUnresolved link scan state (IR10, not benign):\n" + "\n".join(link_notes))

    citations = [schemas.cite("msg", resolved)]
    if user is not None:
        citations.append(schemas.cite("user", user["user_id"]))
    if links:
        # A "link" citation names the message, not one URL (links have no own id
        # in the schema), so one citation covers every link row on this message.
        citations.append(schemas.cite("link", resolved))

    return schemas.ToolResult(
        text="\n".join(lines),
        data={
            "message_id": resolved,
            "message": msg,
            "recipient": user,
            "links": links,
        },
        citations=citations,
    )


def get_message_body(conn: sqlite3.Connection, message_id: str) -> schemas.ToolResult:
    """Body text, fenced as untrusted evidence, plus injection findings.

    This is the only tool through which body text reaches the model's context
    (ADR-004). The four attacker-controlled fields are all scanned, per
    assumption A5.
    """
    resolved, error = resolve_message_id(conn, message_id)
    if error is not None:
        return error

    row = db.one(
        conn,
        "SELECT body_text, subject, sender_display, attachment_names "
        "FROM messages WHERE message_id = ?",
        (resolved,),
    )
    assert row is not None  # resolve_message_id already confirmed existence

    body = row["body_text"] or ""
    findings = injection.scan_message(
        body_text=row["body_text"],
        subject=row["subject"],
        sender_display=row["sender_display"],
        attachment_names=row["attachment_names"],
    )

    short_id = schemas.short(resolved)
    text = f"Body of message {short_id} {schemas.cite('msg', resolved)}:\n\n" + schemas.fence_untrusted(body)

    return schemas.ToolResult(
        text=text,
        data={"message_id": resolved},
        citations=[schemas.cite("msg", resolved)],
        injection_findings=injection.as_dicts(findings),
    )
