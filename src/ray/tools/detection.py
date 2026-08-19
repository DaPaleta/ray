"""The evidence bundle for one message.

`get_detection` merges what were three tools: the analyzer results that exist,
the named analyzers that did not run, the decision, and the remediation.
Coverage is uneven on purpose (plan.md 2.3): an absent analyzer result is
unknown, not benign (IR10), and this tool says so explicitly.
"""

from __future__ import annotations

import sqlite3

from .. import db, schemas
from .messages import resolve_message_id

# The four analyzers that exist in this corpus. plan.md 2.3.
ANALYZERS: tuple[str, ...] = (
    "nlp-analyzer",
    "link-scanner",
    "sender-reputation",
    "stage2",
)


def get_detection(conn: sqlite3.Connection, message_id: str) -> schemas.ToolResult:
    """The analyzer results, the decision, and the remediation for one message."""
    resolved, error = resolve_message_id(conn, message_id)
    if error is not None:
        return error

    short_id = schemas.short(resolved)

    analyzer_rows = db.rows(
        conn,
        "SELECT analyzer, score, verdict, reasoning, ran_at FROM analyzer_results "
        "WHERE message_id = ? ORDER BY analyzer",
        (resolved,),
    )
    ran = {row["analyzer"] for row in analyzer_rows}
    missing = [name for name in ANALYZERS if name not in ran]

    decision = db.one(
        conn,
        "SELECT verdict, attack_type, decided_at, overridden_by, override_reason "
        "FROM decisions WHERE message_id = ?",
        (resolved,),
    )
    remediation = db.one(
        conn,
        "SELECT action, actioned_at, actioned_by FROM remediations WHERE message_id = ?",
        (resolved,),
    )

    lines = [f"Evidence bundle for message {short_id} {schemas.cite('msg', resolved)}"]

    analyzer_headers = ["analyzer", "verdict", "score", "reasoning"]
    analyzer_body = [
        [row["analyzer"], row["verdict"], row["score"], row["reasoning"]]
        for row in analyzer_rows
    ]
    lines.append(
        f"\nAnalyzers that ran ({len(analyzer_rows)} of {len(ANALYZERS)}):\n"
        + schemas.table(analyzer_headers, analyzer_body)
    )

    if missing:
        lines.append(
            "\nAnalyzers that did NOT run (unknown, not benign — IR10): "
            + ", ".join(missing)
        )
    else:
        lines.append("\nAll analyzers ran.")

    if decision is not None:
        attack_type = decision["attack_type"] or "(none)"
        lines.append(
            f"\nDecision: verdict={decision['verdict']}, attack_type={attack_type}, "
            f"decided_at={decision['decided_at']} {schemas.cite('decision', resolved)}"
        )
        if decision["overridden_by"]:
            lines.append(
                "OVERRIDE — this decision was overridden by an analyst:\n"
                f"  overridden_by: {decision['overridden_by']}\n"
                f"  override_reason: {decision['override_reason'] or '(no reason recorded)'}"
            )
    else:
        lines.append(
            "\n"
            + schemas.unknown(
                f"decision for message {short_id}",
                "No decision row exists for this message.",
            )
        )

    if remediation is not None:
        lines.append(
            f"\nRemediation: action={remediation['action']} "
            f"({schemas.inbox_state(remediation['action'])}), "
            f"actioned_at={remediation['actioned_at']}, "
            f"actioned_by={remediation['actioned_by']} "
            f"{schemas.cite('remediation', resolved)}"
        )
    else:
        lines.append(
            "\nRemediation: "
            + schemas.unknown(
                f"remediation for message {short_id}",
                "No remediation row exists. " + schemas.inbox_state(None),
            )
        )

    citations = [schemas.cite("msg", resolved)]
    citations.extend(
        schemas.cite("analyzer", resolved, row["analyzer"]) for row in analyzer_rows
    )
    if decision is not None:
        citations.append(schemas.cite("decision", resolved))
    if remediation is not None:
        citations.append(schemas.cite("remediation", resolved))

    return schemas.ToolResult(
        text="\n".join(lines),
        data={
            "message_id": resolved,
            "analyzers_ran": analyzer_rows,
            "analyzers_missing": missing,
            "decision": decision,
            "remediation": remediation,
        },
        citations=citations,
    )
