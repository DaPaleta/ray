"""The label sets and the metric for the campaign-correlator compile (ADR-012).

ADR-009 built a two-sided metric for the verdict-reviewer: an agreement half, an
adversarial half held out of bootstrapping, and a demonstration that the obvious
shortcut scores 0.0 on the adversarial half. This module does the same for
correlation, where the unit of comparison is a **set of message identifiers**
rather than one verdict label.

The database supplies the labels. Two attacker activities exist in it:

  - **acme-portal.** 15 messages share the link domain `login-verify.acme-portal.co`.
    14 carry `cmp_acme_portal_2026_07`. `93bae03b` carries no `campaign_id` at all.
    Two of the 14, `d0e20c68` and `41fe8ce8`, are recorded `safe` with no attack type.
  - **meridiansupply.** 7 messages from `statements@meridiansupply.com`, all recorded
    `malicious credential_phishing`, and **not one** carries a `campaign_id`. The
    sender domain sends 154 messages in total, so 147 of them are ordinary business
    mail.

Those two activities make three shortcuts fail, and the adversarial half is built so
that each one scores 0.0 or near it:

  1. **Join on `campaign_id`.** Misses `93bae03b`, and misses the meridiansupply
     activity entirely. `campaign_id_baseline` measures it.
  2. **Take the flagged messages only.** Misses `d0e20c68` and `41fe8ce8`, which are
     campaign members recorded `safe`. `flagged_only_baseline` measures it.
  3. **Return everything that shares any indicator.** Loses precision on the
     meridiansupply seed and fails every negative seed. `everything_baseline`
     measures it.

No `import dspy` anywhere in this module, exactly as in `metric.py` (IR8). It must
import cleanly with DSPy absent and with no network access, so the tests run in CI
without the dev dependency and without a key.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from .. import db, schemas
from .metric import two_sided_score

# How many candidate messages one case shows the correlator. A seed such as
# `meridiansupply.com` matches 154 messages, which is more context than a small model
# reads well. Every expected member is always shown; the remainder is filled with
# non-members in received_at order, so the sample is deterministic and the label
# stays reachable from what the model actually sees.
MAX_CANDIDATES = 30

# How many flagged messages from *other* activities join a positive case as
# distractors. A correlator working from `find_messages(flagged_only=True)` sees
# exactly this: several activities at once. Merging two of them is a real failure, and
# without distractors a case where every candidate is a member would score a greedy
# "name everything" answer at 1.0.
DISTRACTORS = 8


@dataclass(frozen=True)
class Seed:
    """One correlation question: an indicator, and how to match it.

    `label` is "positive" when the recorded rows support an attacker activity behind
    the indicator, and "negative" when they do not. `require` holds the 8-character
    identifiers whose absence sets the score to 0.0, which is how the adversarial half
    refuses a shortcut answer.
    """

    indicator: str
    kind: str  # link_domain | sender_domain | sender_email | subject
    label: str  # positive | negative
    require: tuple[str, ...] = ()
    note: str = ""


# --- the two label sets --------------------------------------------------------

# Positive seeds name an indicator behind a real activity. Negative seeds name a
# benign cluster: `tessellate.dev` sends 166 messages and holds no non-safe verdict,
# so a shared sender domain alone is not an attacker activity. The negative seeds are
# what stop a correlator from scoring well by returning everything it is shown.
AGREEMENT_SEEDS: tuple[Seed, ...] = (
    Seed("Open enrolment closes Friday", "subject", "positive",
         note="5 messages, one pretext of the acme-portal activity."),
    Seed("Your August payslip is available", "subject", "positive",
         note="5 messages. Two of them are recorded safe and are still members."),
    Seed("Unusual sign-in blocked", "subject", "positive",
         note="4 messages, the third pretext of the acme-portal activity."),
    Seed("hr-notice@acme-portal.co", "sender_email", "positive",
         note="5 messages from one attacker address."),
    Seed("statements@meridiansupply.com", "sender_email", "positive",
         note="7 messages. No member carries a campaign_id."),
    Seed("billing@quaystone-billing-portal.com", "sender_email", "positive",
         note="5 messages, all released by an analyst, all credential_phishing."),
    Seed("tessellate.dev", "sender_domain", "negative",
         note="166 messages, no non-safe verdict. Not an activity."),
    Seed("quaystone.io", "sender_domain", "negative",
         note="165 messages, no non-safe verdict. The lookalike is a different domain."),
    Seed("atlasparts.net", "sender_domain", "negative",
         note="154 messages, no non-safe verdict."),
    Seed("northgate-logistics.com", "sender_domain", "negative",
         note="153 messages, no non-safe verdict."),
)

# Held out of few-shot bootstrapping, exactly as ADR-009 holds out its 8 rows.
ADVERSARIAL_SEEDS: tuple[Seed, ...] = (
    # Under-inclusion. The expected set holds all 15 messages that share the link
    # domain. `93bae03b` defeats a campaign_id join, and `d0e20c68` and `41fe8ce8`
    # defeat a flagged-only heuristic, so no single-field shortcut passes this case.
    Seed(
        "login-verify.acme-portal.co",
        "link_domain",
        "positive",
        require=("93bae03b", "d0e20c68", "41fe8ce8"),
        note="15 members. A campaign_id join returns 14; a flagged filter returns 13.",
    ),
    # Over-inclusion. The activity is the 7 messages that share the attacker's sender
    # address, not the 154 that share the company's domain.
    Seed(
        "meridiansupply.com",
        "sender_domain",
        "positive",
        note="7 members inside 154 messages from a real company's domain.",
    ),
)


# --- candidate selection and evidence ------------------------------------------

_MATCH_SQL: dict[str, str] = {
    # A message matches a domain when it equals the domain or is a subdomain of it.
    # One direction only, so a seed's label stays predictable. `intel.py` matches both
    # directions at request time, which is correct for retrieval and too broad here.
    "link_domain": (
        "m.message_id IN (SELECT message_id FROM links "
        "WHERE LOWER(domain) = :v OR LOWER(domain) LIKE :v_sub)"
    ),
    "sender_domain": (
        "(LOWER(SUBSTR(m.sender_email, INSTR(m.sender_email, '@') + 1)) = :v "
        "OR LOWER(SUBSTR(m.sender_email, INSTR(m.sender_email, '@') + 1)) LIKE :v_sub)"
    ),
    "sender_email": "LOWER(m.sender_email) = :v",
    "subject": "LOWER(m.subject) LIKE :v_like",
}


def _params(seed: Seed) -> dict[str, str]:
    value = seed.indicator.lower()
    return {"v": value, "v_sub": f"%.{value}", "v_like": f"%{value}%"}


def candidate_rows(conn: sqlite3.Connection, seed: Seed) -> list[sqlite3.Row]:
    """Every message that matches the seed, with the fields a correlator reasons over.

    The recorded verdict and attack type are included, because `find_messages`,
    `domain_intel`, and `entity_graph` all return them at request time.

    `campaign_id` is read here to derive the label, and `build_case` withholds it from
    the evidence the model reads. It is part of the answer key: the labels count a
    message with a `campaign_id` as a member, so showing the field would score a
    correlator on its ability to copy one column. ADR-009 set this precedent —
    `metric.build_evidence` withholds the recorded verdict from the verdict-reviewer for
    exactly the same reason, although `get_detection` returns it at request time.
    """
    clause = _MATCH_SQL[seed.kind]
    return db.rows(
        conn,
        f"""
        SELECT m.message_id, m.received_at, m.sender_email, m.sender_display,
               m.subject, m.spf, m.dkim, m.dmarc,
               COALESCE(m.campaign_id, '') AS campaign_id,
               u.department, u.is_vip,
               d.verdict, COALESCE(d.attack_type, '') AS attack_type,
               (SELECT GROUP_CONCAT(DISTINCT l.url) FROM links l
                 WHERE l.message_id = m.message_id) AS urls,
               (SELECT GROUP_CONCAT(DISTINCT l.scan_verdict) FROM links l
                 WHERE l.message_id = m.message_id) AS scan_verdicts,
               (SELECT MIN(l.is_scanned) FROM links l
                 WHERE l.message_id = m.message_id) AS min_scanned
        FROM messages m
        JOIN decisions d ON d.message_id = m.message_id
        LEFT JOIN users u ON u.user_id = m.recipient_user_id
        WHERE {clause}
        ORDER BY m.received_at, m.message_id
        """,
        _params(seed),
    )


def distractor_rows(conn: sqlite3.Connection, seed: Seed, exclude: set[str]) -> list[sqlite3.Row]:
    """Flagged messages that do NOT match the seed. Deterministic, and capped.

    These belong to other activities, so a correlator must tie each member it names to
    the seed's indicator rather than to the fact that a message is flagged.
    """
    clause = _MATCH_SQL[seed.kind]
    rows = db.rows(
        conn,
        f"""
        SELECT m.message_id, m.received_at, m.sender_email, m.sender_display,
               m.subject, m.spf, m.dkim, m.dmarc,
               COALESCE(m.campaign_id, '') AS campaign_id,
               u.department, u.is_vip,
               d.verdict, COALESCE(d.attack_type, '') AS attack_type,
               (SELECT GROUP_CONCAT(DISTINCT l.url) FROM links l
                 WHERE l.message_id = m.message_id) AS urls,
               (SELECT GROUP_CONCAT(DISTINCT l.scan_verdict) FROM links l
                 WHERE l.message_id = m.message_id) AS scan_verdicts,
               (SELECT MIN(l.is_scanned) FROM links l
                 WHERE l.message_id = m.message_id) AS min_scanned
        FROM messages m
        JOIN decisions d ON d.message_id = m.message_id
        LEFT JOIN users u ON u.user_id = m.recipient_user_id
        WHERE (d.verdict <> 'safe' OR COALESCE(d.attack_type, '') <> '')
          AND NOT ({clause})
        ORDER BY m.received_at, m.message_id
        """,
        _params(seed),
    )
    return [r for r in rows if r["message_id"] not in exclude][:DISTRACTORS]


def _is_member(row: sqlite3.Row) -> bool:
    """Whether a recorded row supports membership in an attacker activity.

    Two recorded signals, and the union of them is what the labels use:
      - the message is flagged: a non-safe verdict, or an attack type;
      - the message carries a `campaign_id`, which records membership directly.

    The union matters. `d0e20c68` and `41fe8ce8` are recorded `safe` with no attack
    type, and both carry `cmp_acme_portal_2026_07`, so a flagged-only reading drops
    two real members.
    """
    return bool(row["verdict"] != "safe" or row["attack_type"] or row["campaign_id"])


@dataclass(frozen=True)
class CorrelationCase:
    """One scored example: the evidence a correlator reads, and the expected set."""

    seed: Seed
    evidence: str
    shown: tuple[str, ...]  # 8-character ids, in the order shown
    expected: frozenset[str]  # 8-character ids
    require: frozenset[str]  # 8-character ids whose absence zeroes the score

    @property
    def is_negative(self) -> bool:
        return not self.expected


def build_case(conn: sqlite3.Connection, seed: Seed) -> CorrelationCase:
    """Build one case: select the candidates, render the evidence, derive the label."""
    rows = candidate_rows(conn, seed)
    members = [r for r in rows if _is_member(r)] if seed.label == "positive" else []
    member_ids = {r["message_id"] for r in members}

    # Every expected member is shown. The rest of the budget goes to non-members in
    # received_at order, so a large benign cluster still gets represented.
    others = [r for r in rows if r["message_id"] not in member_ids]
    shown_rows = members + others[: max(0, MAX_CANDIDATES - len(members))]

    # A positive case also carries flagged messages from other activities. A negative
    # case does not: its question is whether an activity exists behind a benign
    # cluster, and a flagged stranger in that list would make the answer ambiguous.
    if seed.label == "positive":
        shown_rows += distractor_rows(conn, seed, exclude=member_ids)

    shown_rows.sort(key=lambda r: (r["received_at"], r["message_id"]))
    expected = frozenset(schemas.short(r["message_id"]) for r in shown_rows
                         if r["message_id"] in member_ids)
    lines = [
        f"Seed indicator: {seed.indicator} (matched as a {seed.kind.replace('_', ' ')})",
        f"Candidate messages shown: {len(shown_rows)} of {len(rows)} that match the seed.",
        "",
        "Recorded campaign attribution is WITHHELD from this bundle. Correlate on the "
        "shared indicators below.",
        "",
        "Decide which of these candidates belong to one attacker activity. Some, all, "
        "or none of them may belong.",
        "",
    ]
    for row in shown_rows:
        vip = ", VIP" if row["is_vip"] else ""
        scanned = "unscanned" if row["min_scanned"] == 0 else "scanned"
        lines.append(
            f"- {schemas.short(row['message_id'])} | {row['received_at']} | "
            f"{row['sender_display']} <{row['sender_email']}> | "
            f"subject: {row['subject']}"
        )
        lines.append(
            f"    recipient department: {row['department'] or 'unknown'}{vip} | "
            f"spf={row['spf']} dkim={row['dkim']} dmarc={row['dmarc']}"
        )
        lines.append(
            f"    recorded verdict: {row['verdict']} | attack_type: "
            f"{row['attack_type'] or '(none)'} | links: {row['urls'] or '(none)'} "
            f"({scanned}, scan_verdict: {row['scan_verdicts'] or '(none)'})"
        )

    return CorrelationCase(
        seed=seed,
        evidence="\n".join(lines),
        shown=tuple(schemas.short(r["message_id"]) for r in shown_rows),
        expected=expected,
        require=frozenset(seed.require),
    )


def build_cases(conn: sqlite3.Connection, seeds: tuple[Seed, ...]) -> list[CorrelationCase]:
    return [build_case(conn, seed) for seed in seeds]


# --- the metric ----------------------------------------------------------------

_ID_RE = re.compile(r"\b([0-9a-f]{8})(?:[0-9a-f]{24})?\b")


def parse_member_ids(text: str) -> set[str]:
    """Pull 8-character message identifiers out of model text, tolerantly.

    Accepts a bare id, a full 32-character id, and a `[msg:<id>]` citation. Returns
    the 8-character prefixes, which is the form the labels compare on.
    """
    if not text:
        return set()
    return {match.group(1) for match in _ID_RE.finditer(text.lower())}


def score_membership(
    predicted: set[str], expected: frozenset[str], require: frozenset[str] = frozenset()
) -> float:
    """Grade a predicted member set against the expected one.

    The score is the F1 of the two sets, so recall punishes a member the correlator
    missed and precision punishes a message it wrongly included. Then any missing
    required identifier sets the score to 0.0.

    Two edge cases carry the negative seeds:
      - both sets empty: 1.0. The correlator correctly found no activity.
      - expected empty and predicted not: 0.0. It invented an activity.
    """
    if require and not require.issubset(predicted):
        return 0.0
    if not expected:
        return 1.0 if not predicted else 0.0
    if not predicted:
        return 0.0

    hits = len(predicted & expected)
    if not hits:
        return 0.0
    precision = hits / len(predicted)
    recall = hits / len(expected)
    return 2 * precision * recall / (precision + recall)


def score_case(case: CorrelationCase, prediction_text: str) -> float:
    """Score one case from raw model text. Only the shown candidates count.

    An identifier the case never showed is not a hallucination worth a separate
    penalty; it is simply not a member of the candidate set, so it is dropped before
    scoring. Precision is still measured over everything the model named from the set.
    """
    predicted = parse_member_ids(prediction_text) & set(case.shown)
    return score_membership(predicted, case.expected, case.require)


# --- the three shortcut baselines ----------------------------------------------
#
# Each one is the analogue of ADR-009's `constant_safe_baseline`: a correlator that
# needs no model, and that the metric must refuse.


def _baseline(
    conn: sqlite3.Connection,
    predict,
    agreement_seeds: tuple[Seed, ...] = AGREEMENT_SEEDS,
    adversarial_seeds: tuple[Seed, ...] = ADVERSARIAL_SEEDS,
) -> dict[str, float | int]:
    agreement = [
        score_membership(predict(case), case.expected, case.require)
        for case in build_cases(conn, agreement_seeds)
    ]
    adversarial = [
        score_membership(predict(case), case.expected, case.require)
        for case in build_cases(conn, adversarial_seeds)
    ]
    return two_sided_score(agreement, adversarial)


def campaign_id_baseline(conn: sqlite3.Connection) -> dict[str, float | int]:
    """A correlator that joins on `campaign_id`. Scores 0.0 on the adversarial half.

    It misses `93bae03b` on the acme-portal seed, and it returns nothing at all for
    the meridiansupply activity, where no member carries a `campaign_id`.
    """

    def predict(case: CorrelationCase) -> set[str]:
        rows = candidate_rows(conn, case.seed)
        shown = set(case.shown)
        return {
            schemas.short(r["message_id"])
            for r in rows
            if r["campaign_id"] and schemas.short(r["message_id"]) in shown
        }

    return _baseline(conn, predict)


def flagged_only_baseline(conn: sqlite3.Connection) -> dict[str, float | int]:
    """A correlator that takes the flagged messages only.

    It scores 0.0 on the under-inclusion case, because `d0e20c68` and `41fe8ce8` are
    recorded `safe` and are members of the campaign all the same.
    """

    def predict(case: CorrelationCase) -> set[str]:
        rows = candidate_rows(conn, case.seed)
        shown = set(case.shown)
        return {
            schemas.short(r["message_id"])
            for r in rows
            if (r["verdict"] != "safe" or r["attack_type"])
            and schemas.short(r["message_id"]) in shown
        }

    return _baseline(conn, predict)


def everything_baseline(conn: sqlite3.Connection) -> dict[str, float | int]:
    """A correlator that returns every candidate it is shown.

    It fails every negative seed, and it loses most of its precision on the
    over-inclusion case.
    """
    return _baseline(conn, lambda case: set(case.shown))
