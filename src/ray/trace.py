"""The tool-call log for one turn.

This module serves goal 3, visibility. The analyst can see which tool Ray called,
with which arguments, which rows came back, which specialist produced a finding,
and whether the grounding check passed. It also produces the `transcripts/` files.

A trace records what happened. It never changes what happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_PREVIEW = 600


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _preview(text: str, limit: int = MAX_PREVIEW) -> str:
    flat = text.strip()
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result_preview: str = ""
    citations: list[str] = field(default_factory=list)
    injection_findings: list[dict[str, Any]] = field(default_factory=list)
    window: str | None = None
    is_unknown: bool = False
    subagent: str | None = None
    at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "arguments": self.arguments,
            "subagent": self.subagent,
            "citations": self.citations,
            "window": self.window,
            "is_unknown": self.is_unknown,
            "injection_findings": self.injection_findings,
            "result_preview": self.result_preview,
            "at": self.at,
        }


@dataclass
class Turn:
    """One analyst question and Ray's answer, with everything in between."""

    question: str
    answer: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    grounding: dict[str, Any] = field(default_factory=dict)
    memory_proposals: list[dict[str, Any]] = field(default_factory=list)
    graph: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    started_at: str = field(default_factory=_now)
    error: str | None = None
    # True when the grounding check failed and Ray was asked once to re-cite.
    # Recorded so the transcript shows the correction rather than hiding it.
    regrounded: bool = False

    # --- accumulation -----------------------------------------------------

    def record(self, name: str, arguments: dict[str, Any], result: Any = None,
               subagent: str | None = None) -> ToolCall:
        """Record one tool call. `result` may be a ToolResult or a plain string."""
        call = ToolCall(name=name, arguments=dict(arguments), subagent=subagent)
        if result is not None:
            text = getattr(result, "text", None)
            call.result_preview = _preview(text if isinstance(text, str) else str(result))
            call.citations = list(getattr(result, "citations", []) or [])
            call.injection_findings = list(getattr(result, "injection_findings", []) or [])
            call.window = getattr(result, "window", None)
            call.is_unknown = bool(getattr(result, "is_unknown", False))
            data = getattr(result, "data", None)
            if isinstance(data, dict) and "nodes" in data and "edges" in data:
                # The newest graph wins, so the portal renders the relevant one.
                self.graph = {"nodes": data["nodes"], "edges": data["edges"]}
        self.calls.append(call)
        return call

    # --- derived views ----------------------------------------------------

    @property
    def all_citations(self) -> list[str]:
        seen: list[str] = []
        for call in self.calls:
            for citation in call.citations:
                if citation not in seen:
                    seen.append(citation)
        return seen

    @property
    def all_injection_findings(self) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for call in self.calls:
            found.extend(call.injection_findings)
        return found

    @property
    def subagents_used(self) -> list[str]:
        return sorted({c.subagent for c in self.calls if c.subagent})

    @property
    def said_unknown(self) -> bool:
        """True when Ray reported a gap in the data. Criterion 11 needs this."""
        markers = ("NOT IN THE DATA", "does not know", "cannot know", "no click", "no EDR")
        return any(m.lower() in self.answer.lower() for m in markers) or any(
            c.is_unknown for c in self.calls
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "model": self.model,
            "started_at": self.started_at,
            "error": self.error,
            "regrounded": self.regrounded,
            "tool_calls": [c.to_dict() for c in self.calls],
            "subagents_used": self.subagents_used,
            "citations": self.all_citations,
            "grounding": self.grounding,
            "injection_findings": self.all_injection_findings,
            "memory_proposals": self.memory_proposals,
            "graph": self.graph,
        }

    # --- rendering --------------------------------------------------------

    def to_markdown(self) -> str:
        """A transcript a human reads. This is the `transcripts/` format."""
        lines = [
            f"# {self.question}",
            "",
            f"*Model: `{self.model}` · {self.started_at}*",
            "",
            "## Answer",
            "",
            self.answer or "*(no answer produced)*",
            "",
            "## How Ray reached it",
            "",
        ]
        if not self.calls:
            lines.append("*(no tool calls)*")
        for index, call in enumerate(self.calls, start=1):
            where = f" — via `{call.subagent}`" if call.subagent else ""
            args = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items() if v is not None)
            lines.append(f"**{index}. `{call.name}`**{where}")
            if args:
                lines.append(f"   - arguments: `{args}`")
            if call.window:
                lines.append(f"   - window: {call.window}")
            if call.citations:
                lines.append(f"   - rows cited: {' '.join(call.citations[:12])}")
            if call.is_unknown:
                lines.append("   - **result: the data did not support an answer**")
            if call.injection_findings:
                for finding in call.injection_findings:
                    lines.append(
                        f"   - **injection attempt: {finding.get('pattern')}** — "
                        f"`{finding.get('evidence', '')}`"
                    )
            if call.result_preview:
                lines.append("")
                lines.append("   ```")
                for row in call.result_preview.splitlines()[:18]:
                    lines.append(f"   {row}")
                lines.append("   ```")
            lines.append("")

        if self.subagents_used:
            lines += ["## Specialists consulted", "", *(f"- `{s}`" for s in self.subagents_used), ""]

        if self.grounding:
            ok = self.grounding.get("ok")
            lines += [
                "## Grounding check",
                "",
                f"- citations checked: {self.grounding.get('citation_count', 0)}",
                f"- every citation resolves to a real row: **{ok}**",
            ]
            if self.regrounded:
                lines.append(
                    "- the first answer failed this check, so Ray was asked once to "
                    "re-cite from the tool output it already had"
                )
            for failure in self.grounding.get("failures", []):
                lines.append(f"- FAILED `{failure}`")
            lines.append("")

        if self.all_injection_findings:
            lines += [
                "## Prompt-injection attempts found in the evidence",
                "",
                "Ray reported these to the analyst and acted on none of them.",
                "",
            ]
            for finding in self.all_injection_findings:
                lines.append(f"- **{finding.get('pattern')}** — `{finding.get('evidence', '')}`")
            lines.append("")

        if self.memory_proposals:
            lines += ["## Memory proposed this turn", ""]
            for proposal in self.memory_proposals:
                lines.append(
                    f"- `{proposal.get('kind')}`: {proposal.get('content')} "
                    f"(awaiting the analyst's confirmation)"
                )
            lines.append("")

        return "\n".join(lines)


@dataclass
class Session:
    """Every turn in one session. The portal keeps one of these."""

    turns: list[Turn] = field(default_factory=list)
    model: str = ""

    def start(self, question: str) -> Turn:
        turn = Turn(question=question, model=self.model)
        self.turns.append(turn)
        return turn

    @property
    def latest(self) -> Turn | None:
        return self.turns[-1] if self.turns else None

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "turns": [t.to_dict() for t in self.turns]}

    def save_markdown(self, path: Path, title: str | None = None) -> Path:
        parts = [f"# {title}", ""] if title else []
        parts.extend(t.to_markdown() for t in self.turns)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n\n---\n\n".join(parts) + "\n", encoding="utf-8")
        return path

    def save_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
