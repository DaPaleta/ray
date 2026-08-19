"""User lookup.

`find_users` is plan.md 4.4 tool 7. A partial, case-insensitive match on
`display_name` or `email`, filterable by department and VIP flag. When a name
matches more than one user, this returns every match and tells the analyst to
choose — it never picks one for them (plan.md 3.3 edge case 5).
"""

from __future__ import annotations

import sqlite3

from .. import db, schemas


def find_users(
    conn: sqlite3.Connection,
    name: str | None = None,
    email: str | None = None,
    department: str | None = None,
    is_vip: bool | None = None,
    limit: int = 50,
) -> schemas.ToolResult:
    conditions: list[str] = []
    params: list[object] = []

    if name:
        conditions.append("LOWER(display_name) LIKE ?")
        params.append(f"%{name.strip().lower()}%")
    if email:
        conditions.append("LOWER(email) LIKE ?")
        params.append(f"%{email.strip().lower()}%")
    if department:
        conditions.append("LOWER(department) = ?")
        params.append(department.strip().lower())
    if is_vip is not None:
        conditions.append("is_vip = ?")
        params.append(1 if is_vip else 0)

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = max(1, int(limit))

    all_rows = db.rows(
        conn,
        f"SELECT * FROM users WHERE {where} ORDER BY display_name LIMIT ?",
        (*params, limit + 1),
    )
    capped = len(all_rows) > limit
    shown = all_rows[:limit]

    if not shown:
        return schemas.ToolResult(
            text=schemas.unknown(
                "user lookup",
                "No user in the corpus matches the given name, email, department, "
                "or VIP filter.",
            ),
            is_unknown=True,
        )

    headers = ["user_id", "email", "display_name", "department", "title", "is_vip"]
    body = [
        [u["user_id"], u["email"], u["display_name"], u["department"], u["title"], bool(u["is_vip"])]
        for u in shown
    ]
    cap_note = (
        f"(capped at {limit} rows; more match)" if capped else None
    )
    lines = [
        f"Found {len(shown)} user(s)" + (" (more match, capped)" if capped else "") + ":",
        schemas.table(headers, body, cap_note=cap_note),
    ]
    if name and len(shown) > 1:
        lines.append(
            f"\n{len(shown)} users match the name '{name}'. The analyst must choose "
            "which one is meant before Ray acts on a specific user."
        )

    citations = [schemas.cite("user", u["user_id"]) for u in shown]

    return schemas.ToolResult(
        text="\n".join(lines),
        data={"users": [dict(u) for u in shown], "match_count": len(shown), "capped": capped},
        citations=citations,
    )
