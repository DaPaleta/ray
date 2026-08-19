"""Detection of instruction-shaped content in attacker-controlled fields.

This module does not suppress and does not edit. It reports. The analyst needs the
real payload to judge the attack, and a filter that hides it destroys evidence
(ADR-004).

Six messages in the corpus carry a real injection, across five patterns. plan.md
section 2.6 lists them. They are a test corpus: never remove them, never filter
them out (IR4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MAX_EVIDENCE = 160


@dataclass(frozen=True)
class InjectionFinding:
    pattern: str
    evidence: str
    severity: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "evidence": self.evidence,
            "severity": self.severity,
        }


# Each entry is (pattern slug, description, compiled regex).
# The slug names the attacker's technique, which is what the analyst wants to read.
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "role-marker",
        "Fabricates a system or assistant role to impersonate the operator",
        # Anchored to a line start OR preceded by a fence, bracket, or sentence end,
        # so an inline marker mid-body is caught too. A bare "System:" opening a
        # normal sentence is rare in business mail; a false positive here is cheap
        # and a miss is not.
        re.compile(
            r"(?:^|[\n\r]|[-–—>\[\]|*]{2,}\s*|[.!?]\s+)"
            r"\s*(?:-{2,}\s*)?(?:system|assistant|developer|user)\s*:\s*\S",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "instruction-override",
        "Orders the reader to discard its existing instructions",
        re.compile(
            r"ignore\s+(?:all\s+)?(?:prior|previous|preceding|earlier|above)\s+"
            r"(?:instruction|direction|prompt|rule|message)",
            re.IGNORECASE,
        ),
    ),
    (
        "memory-poisoning",
        "Attempts to write a durable trust rule into the agent's memory",
        re.compile(
            r"(?:save|store|remember|persist|commit)\b[^.\n]{0,60}\b"
            r"(?:to|in|into)?\s*(?:your\s+)?memory"
            r"|remember\s+for\s+all\s+future\s+sessions",
            re.IGNORECASE,
        ),
    ),
    (
        "tool-abuse-exfiltration",
        "Orders the agent to call a tool and disclose organizational data",
        re.compile(
            # Allow a multi-word tool name: "call your email lookup tool".
            r"(?:call|invoke|use|run|query)\s+your\s+(?:\w+[\s-]+){1,4}tool"
            r"|(?:include|reply\s+with|send|return|list)\b[^.\n]{0,80}\b"
            r"(?:full\s+list|all|every)\s+(?:of\s+)?(?:\w+\s+){0,3}"
            r"(?:email\s+address|e-?mail|address)",
            re.IGNORECASE,
        ),
    ),
    (
        "fabricated-approval",
        "Claims a prior human review in order to suppress part of the answer",
        re.compile(
            r"(?:reviewed|cleared|approved|whitelisted|allowlisted)\s+by\s+"
            r"(?:the\s+)?(?:soc|security|analyst|team)"
            r"|the\s+analyst\s+has\s+already\s+approved"
            r"|has\s+been\s+reviewed\s+and\s+cleared",
            re.IGNORECASE,
        ),
    ),
    (
        "output-steering",
        "Dictates the agent's verdict, wording, or what it must omit",
        re.compile(
            r"(?:report|state|say|reply|respond|summaris|summariz)\w*\s+"
            r"(?:it\s+|this\s+|that\s+)?(?:as\s+)?(?:benign|safe|clean|'?no\s+threats)"
            r"|do\s+not\s+surface\s+it"
            r"|skip\s+the\s+\w+\s+details"
            r"|end\s+your\s+answer"
            r"|no\s+credential\s+harvesting\s+was\s+involved",
            re.IGNORECASE,
        ),
    ),
    (
        "tooling-directed-note",
        "Addresses the security tooling or an AI assistant directly",
        re.compile(
            r"\[?\s*(?:automated\s+)?note\s+(?:for|to)\s+(?:any\s+)?"
            r"(?:ai|security|automated)\b"
            r"|note\s+to\s+any\s+ai\s+assistant"
            r"|assistant\s+instruction",
            re.IGNORECASE,
        ),
    ),
    (
        "mode-switch",
        "Claims a privileged operating mode to unlock different behaviour",
        re.compile(
            r"(?:you\s+are\s+now\s+in|entering|switch\s+to)\s+\w*\s*"
            r"(?:maintenance|debug|developer|admin|god)\s+mode",
            re.IGNORECASE,
        ),
    ),
]


def _evidence(text: str, match: re.Match[str]) -> str:
    """Quote the matched span with a little context, for the analyst to read."""
    start = max(0, match.start() - 20)
    end = min(len(text), match.end() + 80)
    snippet = " ".join(text[start:end].split())
    if len(snippet) > MAX_EVIDENCE:
        snippet = snippet[: MAX_EVIDENCE - 1] + "…"
    prefix = "…" if start > 0 else ""
    return f"{prefix}{snippet}"


def scan(text: str | None, field: str = "body_text") -> list[InjectionFinding]:
    """Find instruction-shaped content. Returns one finding per distinct pattern."""
    if not text:
        return []
    findings: list[InjectionFinding] = []
    seen: set[str] = set()
    for slug, _description, pattern in _PATTERNS:
        match = pattern.search(text)
        if match and slug not in seen:
            seen.add(slug)
            findings.append(
                InjectionFinding(
                    pattern=f"{slug} in {field}",
                    evidence=_evidence(text, match),
                )
            )
    return findings


def scan_message(
    body_text: str | None = None,
    subject: str | None = None,
    sender_display: str | None = None,
    attachment_names: str | None = None,
) -> list[InjectionFinding]:
    """Scan every attacker-controlled field, not body text alone (assumption A5)."""
    findings: list[InjectionFinding] = []
    for value, field in (
        (body_text, "body_text"),
        (subject, "subject"),
        (sender_display, "sender_display"),
        (attachment_names, "attachment_names"),
    ):
        findings.extend(scan(value, field=field))
    return findings


def as_dicts(findings: list[InjectionFinding]) -> list[dict[str, Any]]:
    return [f.to_dict() for f in findings]


def pattern_catalog() -> list[dict[str, str]]:
    """The techniques this module recognizes. The portal shows this to the analyst."""
    return [{"pattern": slug, "description": desc} for slug, desc, _ in _PATTERNS]
