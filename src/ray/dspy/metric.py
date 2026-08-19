"""The two label sets and the two-sided metric for the verdict-reviewer compile.

ADR-009 requires a metric that cannot be fooled by a constant `safe` answer.
This module builds:

  - `agreement_examples` — a balanced sample of messages whose recorded verdict
    is sound, drawn from the database, never hardcoded row-by-row.
  - `ADVERSARIAL` — the 8 rows whose recorded verdict is wrong (held out of any
    few-shot selection).
  - `build_evidence` — the evidence bundle a verdict-reviewer reasons over. It never
    leaks the recorded verdict, attack type, remediation, or override fields.
  - `score_verdict` / `two_sided_score` / `constant_safe_baseline` — the metric.

No `import dspy` anywhere in this module (IR8). It must import cleanly with
DSPy absent and with no network access, so `tests/test_dspy_metric.py` runs in
CI without the dev dependency and without a key.
"""

from __future__ import annotations

import re
import sqlite3

from .. import db, schemas

# The four analyzers that exist in this corpus. Mirrors tools/detection.py's
# ANALYZERS constant; duplicated here (not imported) so this module has no
# dependency on the request-time tool layer.
ANALYZERS: tuple[str, ...] = (
    "nlp-analyzer",
    "link-scanner",
    "sender-reputation",
    "stage2",
)

# The three verdict labels, ordered by severity.
VERDICT_ORDER: tuple[str, ...] = ("safe", "suspicious", "malicious")

# The 8 rows whose recorded verdict is wrong, mapping message id to the verdict
# Ray should reach instead. Held out of few-shot bootstrapping (ADR-009).
ADVERSARIAL: dict[str, str] = {
    # The 5 released billing@quaystone-billing-portal.com messages. Recorded
    # `safe` with attack_type `credential_phishing` despite an analyst release.
    "c1e587141caa57faaa627f036324e876": "suspicious",
    "567beae60aa4532ba63cbad61e877af1": "suspicious",
    "a3b5e777c16358eba499a8e02e3caaa6": "suspicious",
    "5978f8ed9a4c53129adaeeb21db0a7ff": "suspicious",
    "0641802d9d225a48bf4a9fbe6623c13b": "suspicious",
    # The 2 payslip false negatives. Recorded `safe`; link unscanned but
    # byte-identical to a URL confirmed malicious on 13 sibling messages.
    "d0e20c681476512bb2fd2fb32c280607": "malicious",
    "41fe8ce8b2eb51c4b286f88fc855fd14": "malicious",
    # The CFO impersonation. Recorded `safe` with a NULL attack_type.
    "276266c04c4256d0ad5b1f4f1294a2d6": "malicious",
}


def agreement_examples(conn: sqlite3.Connection, limit: int = 40) -> list[dict[str, str]]:
    """A balanced sample of messages whose recorded verdict is sound.

    Sampled across the distinct verdict values recorded in `decisions`, so the
    set is not overwhelmingly `safe`. Excludes every id in `ADVERSARIAL`.

    Returns a list of `{"message_id": ..., "verdict": ...}` dicts.
    """
    excluded = tuple(ADVERSARIAL.keys())
    placeholders = ",".join("?" for _ in excluded)

    verdict_rows = db.rows(
        conn,
        f"SELECT DISTINCT verdict FROM decisions WHERE message_id NOT IN ({placeholders})",
        excluded,
    )
    verdicts = [row["verdict"] for row in verdict_rows if row["verdict"]]
    if not verdicts:
        return []

    per_verdict = max(1, limit // len(verdicts))
    results: list[dict[str, str]] = []
    for verdict in verdicts:
        rows = db.rows(
            conn,
            "SELECT message_id, verdict FROM decisions "
            f"WHERE verdict = ? AND message_id NOT IN ({placeholders}) "
            "ORDER BY message_id LIMIT ?",
            (verdict, *excluded, per_verdict),
        )
        results.extend({"message_id": r["message_id"], "verdict": r["verdict"]} for r in rows)

    return results[:limit]


def build_evidence(conn: sqlite3.Connection, message_id: str) -> str:
    """The evidence bundle text a verdict-reviewer reasons over.

    Includes sender, recipient with department, subject, SPF/DKIM/DMARC, the
    organization's primary domain, attachment names, every link with
    `is_scanned`/`scan_verdict`, every analyzer result and the names of the
    analyzers that did not run, sibling messages sharing a link domain with
    their scan verdicts, and the body text fenced with `schemas.fence_untrusted`.

    Never includes the recorded verdict, attack type, remediation, or override
    fields (decisions.verdict, decisions.attack_type, decisions.overridden_by,
    decisions.override_reason, remediations.action) — the verdict-reviewer must not
    see the answer it is being scored against.
    """
    msg = db.one(
        conn,
        "SELECT message_id, sender_email, sender_display, recipient_user_id, "
        "subject, body_text, spf, dkim, dmarc, attachment_names "
        "FROM messages WHERE message_id = ?",
        (message_id,),
    )
    if msg is None:
        raise ValueError(f"No message with id {message_id!r}.")

    user = db.one(
        conn,
        "SELECT display_name, department, is_vip FROM users WHERE user_id = ?",
        (msg["recipient_user_id"],),
    )
    org_domain = db.primary_domain(conn)

    links = db.rows(
        conn,
        "SELECT url, domain, is_scanned, scan_verdict FROM links WHERE message_id = ?",
        (message_id,),
    )
    analyzer_rows = db.rows(
        conn,
        "SELECT analyzer, score, verdict, reasoning FROM analyzer_results "
        "WHERE message_id = ? ORDER BY analyzer",
        (message_id,),
    )
    ran = {row["analyzer"] for row in analyzer_rows}
    missing = [name for name in ANALYZERS if name not in ran]

    lines: list[str] = [f"Evidence bundle for message {schemas.short(message_id)}"]

    lines.append(f"\nSender: {msg['sender_display']} <{msg['sender_email']}>")
    if user is not None:
        vip = ", VIP" if user["is_vip"] else ""
        lines.append(f"Recipient: {user['display_name']} (department: {user['department']}{vip})")
    else:
        lines.append("Recipient: no matching user row found")
    lines.append(f"Subject: {msg['subject']}")
    lines.append(
        f"Authentication — SPF: {msg['spf']}, DKIM: {msg['dkim']}, DMARC: {msg['dmarc']}"
    )
    lines.append(f"Organization primary domain (for comparison): {org_domain}")
    lines.append(f"Attachment names: {msg['attachment_names'] or '(none)'}")

    lines.append(f"\nLinks ({len(links)}):")
    if links:
        for link in links:
            scanned = "yes" if link["is_scanned"] else "no (UNSCANNED — not evidence of safety)"
            lines.append(
                f"  - {link['url']} (domain={link['domain']}, scanned={scanned}, "
                f"scan_verdict={link['scan_verdict'] or '(none)'})"
            )
    else:
        lines.append("  (no links)")

    lines.append(f"\nAnalyzer results ({len(analyzer_rows)} of {len(ANALYZERS)} ran):")
    if analyzer_rows:
        for row in analyzer_rows:
            lines.append(
                f"  - {row['analyzer']}: verdict={row['verdict']}, score={row['score']}, "
                f"reasoning={row['reasoning']}"
            )
    else:
        lines.append("  (none ran)")
    if missing:
        lines.append(
            "Analyzers that did NOT run (unknown, not benign): " + ", ".join(missing)
        )
    else:
        lines.append("All analyzers ran.")

    domains = sorted({link["domain"] for link in links if link["domain"]})
    lines.append("\nSibling messages sharing a link domain:")
    sibling_lines: list[str] = []
    for domain in domains:
        siblings = db.rows(
            conn,
            "SELECT message_id, scan_verdict FROM links "
            "WHERE domain = ? AND message_id != ?",
            (domain, message_id),
        )
        for sib in siblings:
            sibling_lines.append(
                f"  - domain {domain}: sibling {schemas.short(sib['message_id'])} "
                f"scan_verdict={sib['scan_verdict'] or '(none)'}"
            )
    lines.extend(sibling_lines if sibling_lines else ["  (none)"])

    lines.append("\nBody:")
    lines.append(schemas.fence_untrusted(msg["body_text"] or ""))

    return "\n".join(lines)


def _parse_verdict(text: str) -> str | None:
    """Tolerantly extract a verdict label from model text.

    Prefers an explicit `Verdict: <label>` marker; falls back to the first
    verdict word found anywhere in the text.
    """
    if not text:
        return None
    lowered = text.lower()

    match = re.search(r"verdict\s*[:\-]\s*(safe|suspicious|malicious)", lowered)
    if match:
        return match.group(1)

    for label in VERDICT_ORDER:
        if re.search(rf"\b{label}\b", lowered):
            return label
    return None


def score_verdict(predicted: str, expected: str) -> float:
    """Grade a predicted verdict against the expected one, on a 3-point scale.

    Exact match: 1.0. Both verdicts are "not safe" but disagree on severity
    (suspicious vs malicious): 0.5, an "adjacent" disagreement. Either verdict
    is `safe` and the other is not: 0.0, an "opposite" disagreement — crossing
    the safe/not-safe boundary is the security-relevant distinction this
    project exists to grade, so it is never merely "adjacent".

    `predicted` is parsed tolerantly (e.g. "Verdict: malicious"). `expected`
    must already be one of `safe`, `suspicious`, `malicious`.
    """
    expected_norm = expected.strip().lower()
    if expected_norm not in VERDICT_ORDER:
        raise ValueError(f"Unknown expected verdict {expected!r}.")

    parsed = _parse_verdict(predicted)
    if parsed is None:
        return 0.0
    if parsed == expected_norm:
        return 1.0
    if {parsed, expected_norm} == {"suspicious", "malicious"}:
        return 0.5
    return 0.0


# The adversarial set gets at least half the weight of the combined score
# (ADR-009): a one-sided metric scores a constant `safe` answer above 98%,
# which is exactly the failure this project exists to catch.
ADVERSARIAL_WEIGHT = 0.6
AGREEMENT_WEIGHT = 1.0 - ADVERSARIAL_WEIGHT


def two_sided_score(
    agreement_results: list[float], adversarial_results: list[float]
) -> dict[str, float | int]:
    """The headline number: agreement score, adversarial score, and their
    weighted combination. The adversarial set is weighted at 60% of `combined`.
    """
    n_agreement = len(agreement_results)
    n_adversarial = len(adversarial_results)

    agreement = sum(agreement_results) / n_agreement if n_agreement else 0.0
    adversarial = sum(adversarial_results) / n_adversarial if n_adversarial else 0.0
    combined = ADVERSARIAL_WEIGHT * adversarial + AGREEMENT_WEIGHT * agreement

    return {
        "agreement": agreement,
        "adversarial": adversarial,
        "combined": combined,
        "n_agreement": n_agreement,
        "n_adversarial": n_adversarial,
    }


def constant_safe_baseline(
    agreement_expected: list[str], adversarial_expected: list[str]
) -> dict[str, float | int]:
    """What a predictor that always answers `safe` scores on the combined metric.

    Its adversarial score is always 0.0: every adversarial target is `suspicious`
    or `malicious`, and `score_verdict` grades any `safe` prediction against a
    non-safe expectation as 0.0 (an "opposite" disagreement). This is the
    demonstration that a one-sided metric would be fooled by a constant answer,
    while the two-sided metric is not.
    """
    agreement_scores = [score_verdict("safe", expected) for expected in agreement_expected]
    adversarial_scores = [score_verdict("safe", expected) for expected in adversarial_expected]
    return two_sided_score(agreement_scores, adversarial_scores)
