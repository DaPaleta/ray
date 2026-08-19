"""Database connections.

The query connection opens read-only, with the SQLite URI flag `mode=ro`. A write
through it raises. That makes the guarantee a property of the process and not of a
prompt, which matters because Ray reads attacker-controlled content.

See docs/decisions/ADR-002-read-only-by-construction.md and IR3.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

# The agent harness runs tools on worker threads, so a connection created on the
# main thread is used from another one. `check_same_thread=False` permits that, and
# this lock serializes access, because a sqlite3 connection is not safe for
# concurrent use even when every statement is a read.
_ACCESS = threading.RLock()

# The one table Ray may write to. See ADR-003.
MEMORY_TABLE = "agent_memory"

# Every table Ray reads. Used by grounding.py to validate a citation target.
READ_TABLES = (
    "messages",
    "links",
    "analyzer_results",
    "decisions",
    "remediations",
    "users",
    "organization",
    "db_meta",
    MEMORY_TABLE,
)


class DatabaseMissing(RuntimeError):
    """The database file is not where the configuration says it is."""


def _check(path: Path) -> Path:
    if not path.is_file():
        raise DatabaseMissing(
            f"No database at {path}. The repository ships one at "
            f"data/ocean_home_task.db; set RAY_DB_PATH to override."
        )
    return path


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open the query connection. Every read tool uses this.

    A write raises sqlite3.OperationalError. Do not remove `mode=ro` (IR3).
    """
    _check(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def connect_memory(path: Path) -> sqlite3.Connection:
    """Open the read-write connection.

    Only src/ray/tools/memory.py may call this, and only for MEMORY_TABLE.
    See ADR-002 and ADR-003.
    """
    _check(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def rows(
    conn: sqlite3.Connection, sql: str, params: Sequence[Any] | dict[str, Any] = ()
) -> list[dict[str, Any]]:
    """Run a parameterized query and return plain dictionaries.

    Always pass values through `params`. Never format a value into `sql`.
    """
    with _ACCESS:
        cur = conn.execute(sql, params)
        try:
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()


def one(
    conn: sqlite3.Connection, sql: str, params: Sequence[Any] | dict[str, Any] = ()
) -> dict[str, Any] | None:
    """Return the first row, or None. An absent row is unknown, not benign (IR10)."""
    result = rows(conn, sql, params)
    return result[0] if result else None


def scalar(
    conn: sqlite3.Connection, sql: str, params: Sequence[Any] | dict[str, Any] = ()
) -> Any:
    """Return the first column of the first row, or None."""
    with _ACCESS:
        cur = conn.execute(sql, params)
        try:
            row = cur.fetchone()
            return row[0] if row is not None else None
        finally:
            cur.close()


def primary_domain(conn: sqlite3.Connection) -> str:
    """The organization's own domain. Everything else is external (assumption A2)."""
    value = scalar(conn, "SELECT primary_domain FROM organization LIMIT 1")
    if not value:
        raise RuntimeError("organization.primary_domain is empty.")
    return str(value)


def organization_name(conn: sqlite3.Connection) -> str:
    value = scalar(conn, "SELECT name FROM organization LIMIT 1")
    return str(value or "the organization")
