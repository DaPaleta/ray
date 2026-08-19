"""Time resolution.

Two traps live here, and both are recorded in plan.md section 2.7.

1. `db_meta.data_as_of` is 2026-08-16T09:00:00Z, but the newest message arrives at
   2026-08-16T17:10:57Z. A window that ends at `data_as_of` drops rows. Every
   relative window therefore takes no upper bound.

2. `received_at` stores `2026-08-16T17:10:57Z`. The SQLite `datetime()` function
   returns `2026-08-09 17:10:57`, with a space where the stored form has a `T`. A
   space sorts below `T`, so a comparison against the `datetime()` form wrongly
   matches rows from earlier on the boundary day: 41 finance rows instead of 38.

   Every boundary is therefore computed in Python and formatted as ISO_FORMAT.
   Never pass a SQLite `datetime()` result into a `received_at` comparison.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from . import db

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Relative phrases the analyst uses, mapped to a day count.
RELATIVE_WINDOWS: dict[str, int] = {
    "today": 1,
    "yesterday": 2,
    "this week": 7,
    "last week": 7,
    "past week": 7,
    "last 7 days": 7,
    "this fortnight": 14,
    "last 14 days": 14,
    "this month": 30,
    "last 30 days": 30,
    "last month": 30,
    "all time": 0,  # 0 means no lower bound either.
}


def parse(value: str) -> datetime:
    """Parse a stored timestamp. Accepts the trailing Z form."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def format_iso(moment: datetime) -> str:
    """Format for comparison against `received_at`. This is the only safe form."""
    return moment.astimezone(timezone.utc).strftime(ISO_FORMAT)


@dataclass(frozen=True)
class Window:
    """A resolved time window. `end` is None when the window has no upper bound."""

    start: str | None
    end: str | None
    label: str
    newest_row: str

    @property
    def description(self) -> str:
        """The sentence Ray shows the analyst. A tool must report its window."""
        if self.start is None and self.end is None:
            return f"the whole recorded window, up to the newest row {self.newest_row}"
        if self.end is None:
            return (
                f"{self.label}: from {self.start} with no upper bound "
                f"(the newest row is {self.newest_row})"
            )
        return f"{self.label}: from {self.start} to {self.end}"

    def clause(self, column: str = "received_at") -> tuple[str, list[str]]:
        """Build the SQL fragment and its parameters for this window."""
        parts: list[str] = []
        params: list[str] = []
        if self.start is not None:
            parts.append(f"{column} >= ?")
            params.append(self.start)
        if self.end is not None:
            parts.append(f"{column} <= ?")
            params.append(self.end)
        return (" AND ".join(parts) if parts else "1=1"), params


def data_as_of(conn: sqlite3.Connection) -> str:
    """The instant db_meta calls the present. Not the same as the newest row."""
    value = db.scalar(conn, "SELECT value FROM db_meta WHERE key = 'data_as_of'")
    return str(value) if value else newest_message(conn)


def newest_message(conn: sqlite3.Connection) -> str:
    """The newest `received_at`. Relative windows anchor here, not on data_as_of."""
    value = db.scalar(conn, "SELECT MAX(received_at) FROM messages")
    if not value:
        raise RuntimeError("The messages table is empty.")
    return str(value)


def oldest_message(conn: sqlite3.Connection) -> str:
    value = db.scalar(conn, "SELECT MIN(received_at) FROM messages")
    return str(value or "")


def match_relative(text: str) -> int | None:
    """Find a relative phrase in analyst text. Returns a day count, or None."""
    lowered = text.strip().lower()
    if lowered in RELATIVE_WINDOWS:
        return RELATIVE_WINDOWS[lowered]

    found = re.fullmatch(r"(?:last|past)\s+(\d{1,3})\s+days?", lowered)
    if found:
        return int(found.group(1))

    for phrase, days in RELATIVE_WINDOWS.items():
        if phrase in lowered:
            return days
    return None


def resolve_window(
    conn: sqlite3.Connection,
    relative: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> Window:
    """Resolve a time window.

    `since` and `until` win when given. Otherwise `relative` is interpreted against
    the newest row. A relative window never takes an upper bound.
    """
    newest = newest_message(conn)

    if since or until:
        return Window(
            start=format_iso(parse(since)) if since else None,
            end=format_iso(parse(until)) if until else None,
            label="the window you gave",
            newest_row=newest,
        )

    if not relative:
        return Window(start=None, end=None, label="all recorded time", newest_row=newest)

    days = match_relative(relative)
    if days is None:
        # Do not guess a window. Report the whole corpus and say so.
        return Window(
            start=None,
            end=None,
            label=f"all recorded time (could not read {relative!r} as a time window)",
            newest_row=newest,
        )
    if days == 0:
        return Window(start=None, end=None, label="all recorded time", newest_row=newest)

    start = parse(newest) - timedelta(days=days)
    return Window(
        start=format_iso(start),
        end=None,
        label=f"the {days} days ending at the newest recorded message",
        newest_row=newest,
    )
