"""Post-hoc verification that every citation in an answer traces to a row.

plan.md section 4.6 names this as mechanism 3, the one that turns requirement 2
("every claim traces to a row") from a prompt promise into a verified property.

This module never edits or filters an answer. It reads the citations the answer
already carries, in the exact format `schemas.cite` produces, and checks each one
against the database. It never raises on malformed input; a check that cannot be
made sense of is reported as a failure, not an exception.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from ray import db
from ray.schemas import CITATION_KINDS

# Matches "[kind:identifier]" or "[kind:identifier/detail]". The identifier and
# detail are whatever schemas.cite put there: an 8-char prefix or a full id, and
# for analyzer citations, an analyzer name.
_CITATION_RE = re.compile(r"\[([a-zA-Z][a-zA-Z0-9_-]*):([^\[\]/]+)(?:/([^\[\]]+))?\]")

# The eleven tool names, mirrored here rather than imported: `subagents.build_tools`
# defines them as closures, and this module sits a layer below it. A test asserts
# that this tuple matches the built registry, so a new tool cannot slip past.
TOOL_NAMES: tuple[str, ...] = (
    "find_messages",
    "get_message",
    "get_message_body",
    "get_detection",
    "domain_intel",
    "entity_graph",
    "find_users",
    "blast_radius",
    "recall",
    "remember",
    "watchlist_sweep",
)

# A tool name in brackets is a claim dressed as a citation. `_CITATION_RE` needs a
# colon, so `[blast_radius]` matched nothing and passed unseen. A live
# incident-response run produced exactly that, which is why this exists.
_PSEUDO_CITATION_RE = re.compile(
    r"\[(" + "|".join(TOOL_NAMES) + r")\]", re.IGNORECASE
)

# A crude heuristic for "this sentence makes a claim". Not exhaustive by design;
# it only needs to catch the common case of an answer with prose and zero
# citations, so the portal can flag it.
_CLAIM_WORDS = re.compile(
    r"\b(is|was|are|were|has|have|shows|indicates|confirms|reports|found|"
    r"malicious|safe|suspicious|quarantined|verdict|phishing|campaign)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CitationCheck:
    raw: str  # the citation as it appeared, e.g. "[msg:93bae03b]"
    kind: str  # "msg", "analyzer", ...
    identifier: str  # the id portion, possibly an 8-char prefix
    detail: str | None  # the analyzer name, for an analyzer citation
    exists: bool
    problem: str | None  # None when fine; else why it failed


@dataclass(frozen=True)
class GroundingReport:
    checks: list[CitationCheck]

    @property
    def ok(self) -> bool:
        """True when every check exists. An empty report is vacuously true."""
        return all(c.exists for c in self.checks)

    @property
    def failures(self) -> list[CitationCheck]:
        return [c for c in self.checks if not c.exists]

    @property
    def citation_count(self) -> int:
        return len(self.checks)

    def summary(self) -> str:
        """One readable line for the portal."""
        if not self.checks:
            return "No citations found in this answer."
        if self.ok:
            return f"All {self.citation_count} citation(s) verified against the data."
        bad = ", ".join(c.raw for c in self.failures)
        return (
            f"{len(self.failures)} of {self.citation_count} citation(s) FAILED "
            f"verification: {bad}"
        )


def extract_citations(text: str) -> list[tuple[str, str, str, str | None]]:
    """Parse every `[kind:identifier]` or `[kind:identifier/detail]` citation.

    Returns a list of (raw, kind, identifier, detail) tuples in order of
    appearance. Never raises; malformed brackets simply do not match.
    """
    if not text:
        return []
    results: list[tuple[str, str, str, str | None]] = []
    for match in _CITATION_RE.finditer(text):
        raw = match.group(0)
        kind = match.group(1)
        identifier = match.group(2)
        detail = match.group(3)
        results.append((raw, kind, identifier, detail))
    return results


def _row_exists(
    conn: sqlite3.Connection, table: str, column: str, identifier: str
) -> bool:
    """Exact prefix match against the mapped table and column.

    schemas.short produces an 8-char prefix, but a full id also matches, because
    `substr(column, 1, len(identifier)) = identifier` matches any value that
    starts with `identifier`, prefix or full.

    Deliberately NOT a SQL `LIKE` match: the identifier comes from the answer
    text under verification, i.e. from the model, i.e. exactly the input this
    module exists to distrust. `LIKE` treats `_` and `%` as wildcards, so a
    fabricated citation such as `[msg:________]` or `[msg:%]` would otherwise
    match every row in the table and verify as real.
    """
    if table not in db.READ_TABLES:
        return False
    try:
        found = db.scalar(
            conn,
            f"SELECT 1 FROM {table} WHERE substr({column}, 1, ?) = ? LIMIT 1",  # nosec: table/column are from CITATION_KINDS, never user input
            (len(identifier), identifier),
        )
        return found is not None
    except sqlite3.Error:
        return False


def _check_one(conn: sqlite3.Connection, raw: str, kind: str, identifier: str, detail: str | None) -> CitationCheck:
    if kind not in CITATION_KINDS:
        return CitationCheck(
            raw=raw,
            kind=kind,
            identifier=identifier,
            detail=detail,
            exists=False,
            problem=f"Unknown citation kind {kind!r}. Not one of {sorted(CITATION_KINDS)}.",
        )

    table, column = CITATION_KINDS[kind]

    if not identifier:
        return CitationCheck(
            raw=raw,
            kind=kind,
            identifier=identifier,
            detail=detail,
            exists=False,
            problem="Empty identifier.",
        )

    if not _row_exists(conn, table, column, identifier):
        return CitationCheck(
            raw=raw,
            kind=kind,
            identifier=identifier,
            detail=detail,
            exists=False,
            problem=f"No row in {table}.{column} matches {identifier!r}.",
        )

    if kind == "analyzer" and detail:
        # The most likely hallucination in the system: claiming an analyzer
        # verdict for an analyzer that never ran on this message. Coverage is
        # uneven (plan.md 2.3): sender-reputation ran on 2 messages, stage2 on 38.
        try:
            found = db.scalar(
                conn,
                "SELECT 1 FROM analyzer_results WHERE substr(message_id, 1, ?) = ? "
                "AND analyzer = ? LIMIT 1",
                (len(identifier), identifier, detail),
            )
        except sqlite3.Error:
            found = None
        if found is None:
            return CitationCheck(
                raw=raw,
                kind=kind,
                identifier=identifier,
                detail=detail,
                exists=False,
                problem=(
                    f"Analyzer {detail!r} has no result for a message matching "
                    f"{identifier!r}. That analyzer either never ran on this "
                    f"message, or the message id is wrong."
                ),
            )

    return CitationCheck(
        raw=raw, kind=kind, identifier=identifier, detail=detail, exists=True, problem=None
    )


def verify(conn: sqlite3.Connection, text: str) -> GroundingReport:
    """Extract every citation from `text` and verify each against the database.

    Never raises. Malformed input yields an empty or partial citation list, and a
    database error on one citation is reported as a failure for that citation,
    not propagated.
    """
    checks: list[CitationCheck] = []
    try:
        parsed = extract_citations(text)
    except Exception:  # pragma: no cover - extract_citations does not raise, defensive only
        parsed = []

    for raw, kind, identifier, detail in parsed:
        try:
            checks.append(_check_one(conn, raw, kind, identifier, detail))
        except Exception as exc:  # defensive: verify must never raise
            checks.append(
                CitationCheck(
                    raw=raw,
                    kind=kind,
                    identifier=identifier,
                    detail=detail,
                    exists=False,
                    problem=f"Verification error: {exc}",
                )
            )

    return GroundingReport(checks=checks)


def find_pseudo_citations(text: str) -> list[str]:
    """Tool names in brackets, in order of appearance and without repeats.

    A tool name is not a row. `[blast_radius]` looks like a citation to a reader and
    to nothing else, so it is reported rather than ignored (IR1).
    """
    seen: list[str] = []
    for match in _PSEUDO_CITATION_RE.finditer(text or ""):
        raw = match.group(0)
        if raw not in seen:
            seen.append(raw)
    return seen


def warn_if_uncited(text: str) -> str | None:
    """Flag an answer that makes claims with no citation at all.

    Returns a warning string when the text looks claim-shaped but carries zero
    citations, else None. This is a heuristic, not a grounding check; verify() is
    the mechanism that checks a citation actually exists.
    """
    if not text or not text.strip():
        return None
    if extract_citations(text):
        return None
    if _CLAIM_WORDS.search(text):
        return (
            "This answer makes claim-shaped statements but carries no citation. "
            "Every claim should trace to a row (IR1)."
        )
    return None
