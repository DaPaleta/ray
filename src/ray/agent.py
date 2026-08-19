"""Builds the deepagents agent and runs one turn.

`create_deep_agent` accepts `model: str | BaseChatModel`, so a ChatAnthropic
instance wires in cleanly. Ray runs Claude Haiku 4.5, not the `gpt-5.6-luna` the
brief names, because the issued OpenAI key never received credit. ADR-005 records
the decision, and NOTES.md discloses it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from . import db, grounding, prompts, subagents
from .config import BRIEF_MODEL, Config, load_config
from .trace import Session, Turn

# A turn that needs several tool calls and a delegation still finishes well inside
# this. The cap stops a runaway loop from consuming the analyst's budget.
MAX_ITERATIONS = 40


@dataclass
class Startup:
    """What the portal shows the analyst when the session opens."""

    model: str
    database: str
    message_count: int
    memory_count: int
    prompt_status: str
    key_present: bool

    @property
    def notes(self) -> list[str]:
        lines = [
            f"Model: {self.model} (the brief names {BRIEF_MODEL}; see NOTES.md)",
            f"Database: {self.database} — {self.message_count} messages",
            f"Organizational memory: {self.memory_count} records",
            f"Adjudicator prompt: {self.prompt_status}",
        ]
        if not self.key_present:
            lines.append("No API key found. Ray cannot answer until one is set.")
        return lines


class Ray:
    """One Ray session. Holds the conversation, the tools, and the trace."""

    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or load_config()
        self.conn: sqlite3.Connection = db.connect_readonly(self.cfg.db_path)
        self.session = Session(model=self.cfg.model)
        self.ctx = subagents.RayContext(cfg=self.cfg, conn=self.conn, session=self.session)
        self.registry = subagents.build_tools(self.ctx)
        self.compiled_prompt, self.prompt_status = subagents.load_compiled_prompt(self.cfg)
        self._agent: Any | None = None
        self._messages: list[Any] = []

    # --- setup ------------------------------------------------------------

    def startup(self) -> Startup:
        return Startup(
            model=self.cfg.model,
            database=str(self.cfg.db_path),
            message_count=int(db.scalar(self.conn, "SELECT COUNT(*) FROM messages") or 0),
            memory_count=int(db.scalar(self.conn, "SELECT COUNT(*) FROM agent_memory") or 0),
            prompt_status=self.prompt_status,
            key_present=self.cfg.has_key,
        )

    def _build_model(self) -> Any:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=self.cfg.model,
            api_key=self.cfg.require_key(),
            temperature=0,
            max_tokens=8000,
            timeout=120,
        )

    @property
    def agent(self) -> Any:
        """Build the agent once, lazily, so no key is needed to construct Ray."""
        if self._agent is None:
            from deepagents import create_deep_agent

            self._agent = create_deep_agent(
                model=self._build_model(),
                tools=list(self.registry.values()),
                system_prompt=prompts.SYSTEM_PROMPT,
                subagents=subagents.build_subagents(self.registry, self.compiled_prompt),
            )
        return self._agent

    # --- one turn ---------------------------------------------------------

    def ask(self, question: str) -> Turn:
        """Answer one question. Records the trace and runs the grounding check."""
        turn = self.session.start(question)
        self._messages.append({"role": "user", "content": question})

        try:
            state = self.agent.invoke(
                {"messages": self._messages},
                config={"recursion_limit": MAX_ITERATIONS},
            )
        except Exception as error:  # noqa: BLE001 - surface any failure to the analyst
            turn.error = f"{type(error).__name__}: {error}"
            turn.answer = (
                "Ray could not complete this turn. The error is recorded in the trace."
            )
            return turn

        produced = state.get("messages", [])
        turn.answer = _final_text(produced)
        # Carry the full history forward, so a later turn sees an earlier one.
        self._messages = list(produced)

        report = grounding.verify(self.conn, turn.answer)
        turn.grounding = {
            "ok": report.ok,
            "citation_count": report.citation_count,
            "failures": [check.raw for check in report.failures],
            "summary": report.summary(),
        }
        uncited = grounding.warn_if_uncited(turn.answer)
        if uncited:
            turn.grounding["uncited_warning"] = uncited
        return turn

    # --- memory confirmation gate (ADR-003 rule 2) ------------------------

    def pending_memory(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self.ctx.store.pending()]

    def confirm_memory(self, proposal_id: str) -> str:
        """Write a proposed record. Only the analyst reaches this."""
        return self.ctx.store.confirm(self.cfg.db_path, self.conn, proposal_id)

    def reject_memory(self, proposal_id: str) -> bool:
        return self.ctx.store.reject(proposal_id)

    def close(self) -> None:
        self.conn.close()


def _final_text(messages: list[Any]) -> str:
    """Pull the assistant's last text out of whatever shape the harness returns."""
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if content is None and isinstance(message, dict):
            if message.get("role") not in (None, "assistant"):
                continue
            content = message.get("content")
        if content is None:
            continue
        if isinstance(content, str):
            if content.strip():
                return content.strip()
            continue
        if isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            joined = "\n".join(p for p in parts if p).strip()
            if joined:
                return joined
    return ""
