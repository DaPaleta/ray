"""Blast-radius reporting. Capability 5a, plan.md section 4.5.

The analyst has already confirmed something is bad. The next question is always
the same: who else got it, and is it still sitting in a mailbox. `blast_radius`
answers that from one free-text indicator: a link domain, a sender email, a
sender domain, a campaign id, a subject, or a message id.

Resolution reuses `intel._resolve_indicator`, the same classifier that
`entity_graph` uses, so a domain indicator is joined through the shared-indicator
relationship (query trap 1) rather than through `campaign_id` alone. A domain is
matched both as a link domain and as a sender domain, exactly as `domain_intel`
does, because `login-verify.acme-portal.co` reaches messages as a link domain and
`quaystone-billing-portal.com` reaches them as a sender domain.

The remediation recommendation is derived, never invented (plan.md 4.5): it names
the messages that are still reachable in an inbox and proposes the action that
their already-quarantined siblings received. Ray recommends. Ray never acts, and
this module states that fact in every answer (docs/vision.md 4.2).
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from .. import db, schemas
from . import intel


def _messages_for_domain(
    conn: sqlite3.Connection, domain_norm: str
) -> tuple[set[str], set[str]]:
    """Message ids reached by a domain, as a link domain and as a sender domain.

    Mirrors `intel.domain_intel`'s two-directional match, including subdomain
    matching in both directions. Returned separately so a caller can cite the
    right source table for each message.
    """
    params = {"d": domain_norm, "d_sub": f"%.{domain_norm}"}
    link_clause = intel._domain_match_clause("l.domain")
    sender_clause = intel._domain_match_clause(intel._sender_domain_expr("m.sender_email"))

    link_ids = {
        r["message_id"]
        for r in db.rows(
            conn,
            f"""
            SELECT DISTINCT l.message_id
            FROM links l JOIN messages m ON m.message_id = l.message_id
            WHERE {link_clause}
            """,
            params,
        )
    }
    sender_ids = {
        r["message_id"]
        for r in db.rows(
            conn,
            f"SELECT message_id FROM messages m WHERE {sender_clause}",
            params,
        )
    }
    return link_ids, sender_ids


def _resolve_message_ids(
    conn: sqlite3.Connection, kind: str, value: str
) -> tuple[set[str], set[str]]:
    """Message ids reached by the resolved indicator.

    Returns (message_ids, link_matched_ids). `link_matched_ids` is the subset
    that matched through the links table, used only to decide which messages
    also earn a `[link:...]` citation.
    """
    if kind == "message":
        return {value}, set()
    if kind == "campaign":
        ids = {
            r["message_id"]
            for r in db.rows(
                conn, "SELECT message_id FROM messages WHERE campaign_id = ?", (value,)
            )
        }
        return ids, set()
    if kind == "sender":
        ids = {
            r["message_id"]
            for r in db.rows(
                conn,
                "SELECT message_id FROM messages WHERE LOWER(sender_email) = ?",
                (value,),
            )
        }
        return ids, set()
    if kind == "domain":
        link_ids, sender_ids = _messages_for_domain(conn, value)
        return link_ids | sender_ids, link_ids
    if kind == "subject":
        ids = {
            r["message_id"]
            for r in db.rows(
                conn,
                "SELECT message_id FROM messages WHERE LOWER(subject) LIKE ?",
                (f"%{value.lower()}%",),
            )
        }
        return ids, set()
    return set(), set()


def blast_radius(
    conn: sqlite3.Connection, indicator: str, limit: int = 100
) -> schemas.ToolResult:
    """Every recipient one indicator reached, with remediation state and a
    derived remediation recommendation. Capability 5a.
    """
    kind, value, note = intel._resolve_indicator(conn, indicator)
    if kind is None:
        return schemas.ToolResult(
            text=schemas.unknown(f"blast radius for '{indicator}'", note),
            is_unknown=True,
            data={"messages": []},
        )

    message_ids, link_matched_ids = _resolve_message_ids(conn, kind, value)
    if not message_ids:
        return schemas.ToolResult(
            text=schemas.unknown(
                f"blast radius for '{indicator}'",
                f"{note}, but no message in the corpus matches this resolved indicator.",
            ),
            is_unknown=True,
            data={"messages": [], "resolved_kind": kind, "resolved_value": value},
        )

    placeholders = ",".join("?" * len(message_ids))
    id_params = tuple(message_ids)
    detail_rows = db.rows(
        conn,
        f"""
        SELECT m.message_id, m.received_at, m.sender_email, m.subject,
               m.recipient_user_id, u.display_name, u.department, u.is_vip,
               d.verdict, d.attack_type, d.overridden_by, d.override_reason,
               r.action
        FROM messages m
        LEFT JOIN users u ON u.user_id = m.recipient_user_id
        LEFT JOIN decisions d ON d.message_id = m.message_id
        LEFT JOIN remediations r ON r.message_id = m.message_id
        WHERE m.message_id IN ({placeholders})
        ORDER BY m.received_at
        """,
        id_params,
    )

    total = len(detail_rows)
    limit = max(1, int(limit))
    capped = total > limit
    shown_rows = detail_rows[:limit]

    citations: list[str] = []
    for r in detail_rows:
        mid = r["message_id"]
        citations.append(schemas.cite("msg", mid))
        citations.append(schemas.cite("decision", mid))
        if r["action"] is not None:
            citations.append(schemas.cite("remediation", mid))
        if r["recipient_user_id"]:
            citations.append(schemas.cite("user", r["recipient_user_id"]))
        if mid in link_matched_ids:
            citations.append(schemas.cite("link", mid))

    recipients = {r["recipient_user_id"] for r in detail_rows if r["recipient_user_id"]}
    department_counts: Counter[str] = Counter(
        r["department"] for r in detail_rows if r["department"]
    )
    vip_hits = [r for r in detail_rows if r["is_vip"]]

    quarantined = [r for r in detail_rows if (r["action"] or "").strip().lower() == "quarantined"]
    live_rows = [r for r in detail_rows if schemas.is_in_inbox(r["action"])]
    overridden_rows = [
        r for r in detail_rows if (r["overridden_by"] or "").strip() != ""
    ]

    action_counts: Counter[str] = Counter()
    for r in detail_rows:
        if r["action"] is None:
            action_counts["no recorded remediation"] += 1
        else:
            action_counts[r["action"]] += 1

    # --- render -----------------------------------------------------------
    lines = [
        f"Blast radius for '{indicator}': {note}",
        f"Reached {total} message(s), {len(recipients)} distinct recipient(s), "
        f"across {len(department_counts)} department(s).",
    ]

    body = []
    for r in shown_rows:
        body.append(
            [
                schemas.short(r["message_id"]),
                r["received_at"],
                r["display_name"] or r["recipient_user_id"] or "(unknown recipient)",
                r["department"] or "(unknown)",
                "VIP" if r["is_vip"] else "",
                r["verdict"],
                r["attack_type"] or "",
                r["action"] if r["action"] is not None else "(none recorded)",
                schemas.inbox_state(r["action"]),
            ]
        )
    cap_note = None
    if capped:
        cap_note = f"... capped at {limit} of {total} matching messages"
    lines.append(
        schemas.table(
            [
                "id",
                "received_at",
                "recipient",
                "department",
                "vip",
                "verdict",
                "attack_type",
                "action",
                "inbox_state",
            ],
            body,
            cap_note=cap_note,
        )
    )

    lines.append("\nPer-department breakdown:")
    for department, count in department_counts.most_common():
        lines.append(f"  {department}: {count}")

    if vip_hits:
        lines.append(
            "\nVIP hits (called out separately, they matter more): "
            + ", ".join(
                f"{r['display_name']} ({r['department']}, msg {schemas.short(r['message_id'])})"
                for r in vip_hits
            )
        )
    else:
        lines.append("\nNo VIP recipient was reached.")

    lines.append("\nRemediation state:")
    for action, count in action_counts.most_common():
        lines.append(f"  {action}: {count}")

    if live_rows:
        lines.append(
            f"\nStill reachable in an inbox — {len(live_rows)} message(s): "
            + ", ".join(schemas.short(r["message_id"]) for r in live_rows)
            + ". Only `quarantined` removes a message; `none`, `released`, and an "
            "absent remediation row all leave it in the inbox (assumption A3)."
        )
    else:
        lines.append("\nEvery message on this indicator is quarantined; none remain in an inbox.")

    if overridden_rows:
        lines.append(
            "\nAnalyst override(s) on this indicator — a released message is the "
            "most dangerous kind of live message:"
        )
        for r in overridden_rows:
            lines.append(
                f"  {schemas.short(r['message_id'])}: overridden by {r['overridden_by']}, "
                f"reason: \"{r['override_reason']}\""
            )

    # --- recommendation (derived, not invented) ----------------------------
    if quarantined and live_rows:
        lines.append(
            f"\nRECOMMENDATION: quarantine {', '.join(schemas.short(r['message_id']) for r in live_rows)} "
            f"— {len(live_rows)} message(s) still in an inbox on this indicator. "
            f"This matches the action already taken on {len(quarantined)} sibling "
            "message(s) sharing the same indicator. Ray recommends this action; Ray "
            "cannot quarantine or release any message itself."
        )
    elif live_rows:
        lines.append(
            f"\nNo sibling message on this indicator has been quarantined, so no "
            f"remediation baseline exists to recommend from. {len(live_rows)} "
            f"message(s) remain in an inbox and need direct analyst review: "
            + ", ".join(schemas.short(r["message_id"]) for r in live_rows)
            + ". Ray recommends only; Ray cannot quarantine or release any message."
        )
    else:
        lines.append(
            "\nNo further remediation is recommended; every message on this "
            "indicator is already quarantined. Ray cannot quarantine or release "
            "any message."
        )

    data: dict[str, Any] = {
        "resolved_kind": kind,
        "resolved_value": value,
        "message_count": total,
        "recipient_count": len(recipients),
        "department_count": len(department_counts),
        "department_breakdown": dict(department_counts),
        "vip_hit_count": len(vip_hits),
        "quarantined_count": len(quarantined),
        "live_message_ids": [r["message_id"] for r in live_rows],
        "overridden_message_ids": [r["message_id"] for r in overridden_rows],
        "messages": detail_rows,
        "capped": capped,
    }

    return schemas.ToolResult(text="\n".join(lines), data=data, citations=citations)
