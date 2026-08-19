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

from ..tools.memory import MemoryRefused, recall

INDEX_PATH = Path(__file__).with_name("index.html")


class AskRequest(BaseModel):
    question: str


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
