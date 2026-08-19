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
    prompt_statuses: list[str]
    key_present: bool

    @property
    def prompt_status(self) -> str:
        """One line for the portal header. The full list goes into `notes`."""
        compiled = [line for line in self.prompt_statuses if "compiled from" in line]
        return (
            f"{len(compiled)} of {len(self.prompt_statuses)} specialist prompts compiled"
            if compiled
            else "hand-written (no compiled artifact found)"
        )

    @property
    def prompt_detail(self) -> list[str]:
        """One line per specialist. The CLI prints these; the portal header does not.

        `notes` stays four lines, because the portal renders it as a row of chips and
        five indented lines would read as noise there.
        """
        return list(self.prompt_statuses)

    @property
    def notes(self) -> list[str]:
        lines = [
            f"Model: {self.model} (the brief names {BRIEF_MODEL}; see NOTES.md)",
            f"Database: {self.database} — {self.message_count} messages",
            f"Organizational memory: {self.memory_count} records",
            f"Specialist prompts: {self.prompt_status}",
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
        self.compiled_prompts, self.prompt_statuses = subagents.load_compiled_prompts(
            self.cfg
        )
        self._agent: Any | None = None
        self._messages: list[Any] = []

    # --- setup ------------------------------------------------------------

    def startup(self) -> Startup:
        return Startup(
            model=self.cfg.model,
            database=str(self.cfg.db_path),
            message_count=int(db.scalar(self.conn, "SELECT COUNT(*) FROM messages") or 0),
            memory_count=int(db.scalar(self.conn, "SELECT COUNT(*) FROM agent_memory") or 0),
            prompt_statuses=list(self.prompt_statuses),
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
                subagents=subagents.build_subagents(self.ctx, self.compiled_prompts),
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

        self._ground(turn)

        # One corrective pass when grounding fails. A small model reliably writes a
        # good answer and then cites it badly — inventing a tool name such as
        # `[domain_intel]`, or omitting citations altogether. The tool output it
        # needs is already in its context, so asking once is cheap and it fixes the
        # answer rather than merely reporting it broken.
        if self._needs_recite(turn):
            turn.regrounded = True
            self._recite(turn)

        return turn

    # --- grounding and the corrective pass --------------------------------

    def _ground(self, turn: Turn) -> None:
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
        pseudo = grounding.find_pseudo_citations(turn.answer)
        if pseudo:
            turn.grounding["pseudo_citations"] = pseudo
            turn.grounding["summary"] = (
                turn.grounding["summary"]
                + " A tool name in brackets is not a citation: "
                + ", ".join(pseudo)
                + "."
            )

    def _needs_recite(self, turn: Turn) -> bool:
        if turn.error or not turn.answer.strip():
            return False
        grounded = turn.grounding
        if grounded.get("failures") or grounded.get("pseudo_citations"):
            return True
        return bool(grounded.get("uncited_warning")) and grounded.get("citation_count") == 0

    def _recite(self, turn: Turn) -> None:
        """Ask once for the same answer with real citations. Never changes findings."""
        failures = turn.grounding.get("failures") or []
        pseudo = turn.grounding.get("pseudo_citations") or []
        if failures and pseudo:
            problem = (
                "these citations do not match any row in the database: "
                + ", ".join(failures[:8])
                + "; and these are tool names, not rows: "
                + ", ".join(pseudo[:8])
            )
        elif pseudo:
            problem = "these are tool names, not rows: " + ", ".join(pseudo[:8])
        elif failures:
            problem = (
                "these citations do not match any row in the database: "
                + ", ".join(failures[:8])
            )
        else:
            problem = "your answer carries no citation at all"

        correction = (
            f"GROUNDING CHECK FAILED — {problem}.\n\n"
            "Rewrite your previous answer. Keep every finding and every conclusion "
            "exactly as they were; this is a citation problem, not a analysis "
            "problem. Replace each unsupported reference with the real row citations "
            "from the tool output already in this conversation.\n\n"
            "A citation is one of these forms and nothing else:\n"
            "  [msg:<8-char message id>]      [decision:<8-char message id>]\n"
            "  [analyzer:<8-char id>/<analyzer name>]  [link:<8-char message id>]\n"
            "  [remediation:<8-char message id>]       [user:<user id>]\n"
            "  [mem:<memory id>]\n\n"
            "One bracket holds exactly ONE identifier. "
            "[decision:41fe8ce8, decision:d0e20c68] is two ids in one bracket and fails "
            "the check; write [decision:41fe8ce8] [decision:d0e20c68] instead.\n\n"
            "A tool name in brackets, such as [domain_intel] or [find_messages], is "
            "NOT a citation. Use the message ids the tools returned. Do not invent an "
            "id, and do not cite an analyzer that did not run on that message. If a "
            "claim has no row behind it, drop the claim rather than citing nothing."
        )
        self._messages.append({"role": "user", "content": correction})
        try:
            state = self.agent.invoke(
                {"messages": self._messages},
                config={"recursion_limit": MAX_ITERATIONS},
            )
        except Exception as error:  # noqa: BLE001
            turn.grounding["recite_error"] = f"{type(error).__name__}: {error}"
            return

        produced = state.get("messages", [])
        rewritten = _final_text(produced)
        if rewritten.strip():
            turn.answer = rewritten
            self._messages = list(produced)
            self._ground(turn)

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
