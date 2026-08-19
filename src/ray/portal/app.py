"""FastAPI application for the analyst portal. ADR-007.

Holds no query and no threat logic (docs/structure.md section 2). The one
retrieval this module performs — reading the confirmed memory records for
`GET /api/state` — goes through the existing `tools/memory.recall` tool, never
through a query written here.

`create_app(ray)` builds the app around one already-constructed `Ray` instance,
so a test can exercise it without a model and without starting a server.
`serve(ray)` is the only function that talks to uvicorn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from ..config import REPO_ROOT
from ..tools.memory import MemoryRefused, recall

INDEX_PATH = Path(__file__).with_name("index.html")

# Explicit allow-list; no path parameter is accepted (prevents traversal). ADR-015.
_DOC_SETS: dict[str, list[str]] = {
    "overview": [
        "docs/vision.md",
        "NOTES.md",
        "docs/decisions/ADR-001-typed-tools-over-raw-sql.md",
        "docs/decisions/ADR-002-read-only-by-construction.md",
        "docs/decisions/ADR-003-memory-provenance-and-confirmation.md",
        "docs/decisions/ADR-004-body-text-isolation.md",
        "docs/decisions/ADR-007-local-web-portal-as-the-interface.md",
    ],
    "execution": [
        "transcripts/01-finance-team-this-week.md",
        "transcripts/02-why-is-the-mailbox-message-malicious.md",
        "transcripts/03-acme-portal-indicator-and-what-ray-cannot-know.md",
        "transcripts/04-cfo-policy-remembered-then-applied.md",
        "transcripts/05-blast-radius-and-remediation.md",
        "transcripts/06-prompt-injection-reported-not-obeyed.md",
        "transcripts/07-watchlist-learned-from-analyst-overrides.md",
        "transcripts/08-soc-workflow-triage-then-response.md",
        "docs/vision.md",
    ],
    "decisions": [
        "docs/tasks/ray-email-threat-investigator/conversation.md",
        "docs/tasks/ray-soc-role-subagents/conversation.md",
        "docs/decisions/ADR-001-typed-tools-over-raw-sql.md",
        "docs/decisions/ADR-002-read-only-by-construction.md",
        "docs/decisions/ADR-003-memory-provenance-and-confirmation.md",
        "docs/decisions/ADR-004-body-text-isolation.md",
        "docs/decisions/ADR-005-model-boundary-and-offline-testability.md",
        "docs/decisions/ADR-006-commit-the-supplied-database.md",
        "docs/decisions/ADR-007-local-web-portal-as-the-interface.md",
        "docs/decisions/ADR-008-specialized-subagents.md",
        "docs/decisions/ADR-009-dspy-compiles-offline.md",
        "docs/decisions/ADR-010-watchlist-instead-of-real-time-alerts.md",
        "docs/decisions/ADR-011-soc-role-subagent-roster.md",
        "docs/decisions/ADR-012-compile-every-labelled-prompt.md",
        "docs/decisions/ADR-013-plain-name-for-the-verdict-specialist.md",
        "docs/decisions/ADR-014-poll-a-progress-endpoint-while-a-turn-runs.md",
        "docs/decisions/ADR-015-docs-assistant-separate-from-grounded-agent.md",
    ],
    "tech": [
        "NOTES.md",
        "AGENTS.md",
        "docs/decisions/ADR-008-specialized-subagents.md",
        "docs/decisions/ADR-009-dspy-compiles-offline.md",
        "docs/decisions/ADR-011-soc-role-subagent-roster.md",
        "docs/decisions/ADR-012-compile-every-labelled-prompt.md",
        "docs/decisions/ADR-001-typed-tools-over-raw-sql.md",
        "docs/decisions/ADR-004-body-text-isolation.md",
        "docs/vision.md",
    ],
}

_DOCS_SYSTEM = """You are a documentation assistant for Ray, an email-threat investigator agent.
Answer questions from the provided repository documents only.
Be concise and direct. Quote exact numbers and file paths when they appear in the docs.
Do not invent information not present in the documents.
You carry no citation requirement and no database access — say so if asked."""


class AskRequest(BaseModel):
    question: str


class DocsAskRequest(BaseModel):
    question: str
    tab: str = "overview"


class ProposalRequest(BaseModel):
    proposal_id: str


def _memory_records(ray: Any) -> list[dict[str, Any]]:
    """The confirmed `agent_memory` rows, via the `recall` tool.

    Returns an empty list rather than raising when `ray` carries no connection
    (a bare test double, or a `ray` handed in before it is fully wired up).
    """
    conn = getattr(ray, "conn", None)
    if conn is None:
        return []
    try:
        result = recall(conn, limit=200)
    except Exception:  # noqa: BLE001 - the state endpoint must never 500
        return []
    return list(result.data.get("records", []))


def create_app(ray: Any) -> FastAPI:
    """Build the FastAPI app around one Ray session. Touches no `ray` attribute
    until a request arrives, so this never requires an API key to construct.
    """
    app = FastAPI(title="Ray — analyst portal")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_PATH.read_text(encoding="utf-8")

    @app.get("/api/state")
    def get_state() -> dict[str, Any]:
        startup = ray.startup()
        return {
            "notes": startup.notes,
            "model": startup.model,
            "database": startup.database,
            "message_count": startup.message_count,
            "memory_count": startup.memory_count,
            "prompt_status": startup.prompt_status,
            "prompt_detail": startup.prompt_detail,
            "key_present": startup.key_present,
            "memory_records": _memory_records(ray),
            "pending_memory": ray.pending_memory(),
        }

    @app.post("/api/ask")
    def ask(payload: AskRequest) -> dict[str, Any]:
        # A plain `def` route: FastAPI runs it in a threadpool, so the blocking
        # model call does not block the event loop. A turn can take 30s or more.
        question = (payload.question or "").strip()
        if not question:
            return JSONResponse(status_code=400, content={"error": "question is required"})
        turn = ray.ask(question)
        return turn.to_dict()

    @app.get("/api/progress")
    def progress() -> dict[str, Any]:
        """Liveness and per-turn progress, for the portal's thinking indicator.

        The page polls this while a `POST /api/ask` is in flight, so it reads
        `Turn` attributes only. It runs no query, and it never calls
        `ray.startup()` — a sqlite connection is bound to the thread that made
        it, and the agent is using that connection in the threadpool worker.

        `turn_count` exists so the page can tell this turn from the last one.
        `ray.ask` calls `session.start()` inside the worker, so an early poll
        still sees the previous, finished turn.

        `steps` holds *completed* tool calls. A call is recorded when the tool
        returns, so nothing here reports a call that is still running.
        """
        session = getattr(ray, "session", None)
        turns = list(getattr(session, "turns", None) or [])
        if not turns:
            return {
                "alive": True,
                "turn_count": 0,
                "steps": [],
                "done": False,
                "error": False,
            }
        turn = turns[-1]
        calls = list(getattr(turn, "calls", None) or [])
        return {
            "alive": True,
            "turn_count": len(turns),
            "started_at": getattr(turn, "started_at", None),
            "steps": [
                {
                    "name": getattr(call, "name", ""),
                    "subagent": getattr(call, "subagent", None),
                }
                for call in calls
            ],
            "done": bool(getattr(turn, "answer", "") or getattr(turn, "error", None)),
            # `ask` writes a stand-in answer on the error path too, so `done`
            # alone cannot tell a drafted answer from a failed turn.
            "error": bool(getattr(turn, "error", None)),
        }

    @app.post("/api/memory/confirm")
    def confirm_memory(payload: ProposalRequest) -> dict[str, Any]:
        try:
            memory_id = ray.confirm_memory(payload.proposal_id)
        except MemoryRefused as refusal:
            return JSONResponse(status_code=400, content={"error": str(refusal)})
        return {"memory_id": memory_id}

    @app.post("/api/memory/reject")
    def reject_memory(payload: ProposalRequest) -> dict[str, Any]:
        ok = ray.reject_memory(payload.proposal_id)
        if not ok:
            return JSONResponse(
                status_code=400,
                content={"error": f"No pending proposal {payload.proposal_id!r}."},
            )
        return {"ok": True}

    @app.get("/api/docs/{key}")
    def get_docs(key: str) -> PlainTextResponse:
        """Return the concatenated markdown for a named doc set (ADR-015).

        Only keys in `_DOC_SETS` are accepted. Any unknown key returns 404 so the
        caller can never probe arbitrary filesystem paths.
        """
        if key not in _DOC_SETS:
            return JSONResponse(status_code=404, content={"error": f"Unknown doc set: {key!r}"})
        parts: list[str] = []
        for rel in _DOC_SETS[key]:
            path = REPO_ROOT / rel
            if path.exists():
                parts.append(f"# --- {rel} ---\n\n{path.read_text(encoding='utf-8')}")
        body = "\n\n".join(parts) if parts else "*(no documents found)*"
        return PlainTextResponse(body, media_type="text/plain; charset=utf-8")

    @app.post("/api/docs-ask")
    def docs_ask(payload: DocsAskRequest) -> dict[str, Any]:
        """Answer a question from repo docs, with no DB access and no grounding pass.

        The API key is read here, not at construction time, so `create_app` still
        builds keyless and tests pass with no env. ADR-015.
        """
        api_key = getattr(ray.cfg, "api_key", None)
        if not api_key:
            return JSONResponse(
                status_code=503,
                content={"error": "No API key — set OCEAN_ANTHROPIC_KEY to use the docs assistant."},
            )

        tab = payload.tab if payload.tab in _DOC_SETS else "overview"
        context_parts: list[str] = []
        for rel in _DOC_SETS[tab]:
            path = REPO_ROOT / rel
            if path.exists():
                context_parts.append(f"=== {rel} ===\n{path.read_text(encoding='utf-8')}")
        context = "\n\n".join(context_parts) if context_parts else "(no documents)"

        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=getattr(ray.cfg, "model", "claude-haiku-4-5-20251001"),
                max_tokens=1024,
                system=_DOCS_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": f"Documents:\n\n{context}\n\n---\n\nQuestion: {payload.question}",
                    }
                ],
            )
            answer = message.content[0].text if message.content else "(no answer)"
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=500, content={"error": str(exc)})

        return {"answer": answer}

    @app.get("/api/message/{message_id}")
    def get_message_preview(message_id: str) -> dict[str, Any]:
        """Return safe header + verdict data for one message. Never returns body_text (ADR-004)."""
        conn = getattr(ray, "conn", None)
        if conn is None:
            return JSONResponse(status_code=503, content={"error": "No database connection."})

        import sqlite3 as _sqlite3

        try:
            mid = (message_id or "").strip()
            if not mid:
                return JSONResponse(status_code=400, content={"error": "message_id is required"})

            # Resolve prefix → full id
            if len(mid) < 32:
                rows = conn.execute(
                    "SELECT message_id FROM messages WHERE message_id LIKE ? ORDER BY message_id",
                    (f"{mid}%",),
                ).fetchall()
                if not rows:
                    return JSONResponse(status_code=404, content={"error": f"No message matches prefix {mid!r}"})
                if len(rows) > 1:
                    return JSONResponse(status_code=400, content={"error": f"Prefix {mid!r} is ambiguous ({len(rows)} matches)"})
                mid = rows[0][0]
            else:
                row = conn.execute(
                    "SELECT message_id FROM messages WHERE message_id = ?", (mid,)
                ).fetchone()
                if row is None:
                    return JSONResponse(status_code=404, content={"error": f"No message with id {mid!r}"})

            msg = conn.execute(
                "SELECT message_id, received_at, sender_email, sender_display, "
                "recipient_user_id, subject, spf, dkim, dmarc, attachment_names, campaign_id "
                "FROM messages WHERE message_id = ?",
                (mid,),
            ).fetchone()
            if msg is None:
                return JSONResponse(status_code=404, content={"error": "Message not found"})

            keys = ["message_id", "received_at", "sender_email", "sender_display",
                    "recipient_user_id", "subject", "spf", "dkim", "dmarc",
                    "attachment_names", "campaign_id"]
            msg_dict = dict(zip(keys, msg))

            user = conn.execute(
                "SELECT display_name, department, is_vip FROM users WHERE user_id = ?",
                (msg_dict["recipient_user_id"],),
            ).fetchone()

            decision = conn.execute(
                "SELECT verdict, attack_type, confidence FROM decisions WHERE message_id = ?",
                (mid,),
            ).fetchone()

            remediation = conn.execute(
                "SELECT action FROM remediations WHERE message_id = ?",
                (mid,),
            ).fetchone()

            links_rows = conn.execute(
                "SELECT url, domain, is_scanned, scan_verdict FROM links WHERE message_id = ?",
                (mid,),
            ).fetchall()
            links = [
                {"url": r[0], "domain": r[1], "is_scanned": r[2], "scan_verdict": r[3]}
                for r in links_rows
            ]

            return {
                "message_id": mid,
                "subject": msg_dict["subject"],
                "received_at": msg_dict["received_at"],
                "sender_email": msg_dict["sender_email"],
                "sender_display": msg_dict["sender_display"],
                "spf": msg_dict["spf"],
                "dkim": msg_dict["dkim"],
                "dmarc": msg_dict["dmarc"],
                "attachment_names": msg_dict["attachment_names"],
                "campaign_id": msg_dict["campaign_id"],
                "recipient": {
                    "name": user[0] if user else None,
                    "department": user[1] if user else None,
                    "is_vip": bool(user[2]) if user else False,
                } if user else None,
                "verdict": decision[0] if decision else None,
                "attack_type": decision[1] if decision else None,
                "confidence": decision[2] if decision else None,
                "remediation": remediation[0] if remediation else None,
                "links": links,
            }
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=500, content={"error": str(exc)})

    @app.get("/api/transcript")
    def transcript() -> PlainTextResponse:
        turns = ray.session.turns
        if not turns:
            body = "*(no turns yet)*\n"
        else:
            body = "\n\n---\n\n".join(t.to_markdown() for t in turns) + "\n"
        return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")

    return app


def serve(ray: Any) -> None:
    """Run the portal. `python -m ray` calls this via `command_portal`."""
    import uvicorn

    app = create_app(ray)
    uvicorn.run(app, host=ray.cfg.host, port=ray.cfg.port)
