"""Environment variables and defaults.

This module holds every default. No other module reads os.environ.
See docs/decisions/ADR-005-model-boundary-and-offline-testability.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# The repository root, resolved from this file: src/ray/config.py -> ray/
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_DB_PATH = "data/ocean_home_task.db"
DEFAULT_PROMPTS_DIR = "prompts"

# One compiled artifact per specialist, named for the specialist (ADR-012). A
# specialist absent from this map carries a hand-written prompt only, because the
# database holds no label for what it outputs (IR11).
COMPILED_ARTIFACTS: dict[str, str] = {
    "verdict-reviewer": "reviewer.compiled.json",
    "campaign-correlator": "correlator.compiled.json",
}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# The brief specifies gpt-5.6-luna. Ray runs Haiku instead, because the issued
# OpenAI key never received credit. NOTES.md discloses this. See ADR-005 and IR6.
BRIEF_MODEL = "gpt-5.6-luna"

KEY_VAR = "OCEAN_ANTHROPIC_KEY"


def _resolve(value: str) -> Path:
    """Resolve a path against the repository root when it is relative."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (REPO_ROOT / path)


@dataclass(frozen=True)
class Config:
    db_path: Path
    model: str
    # repr=False so the key cannot reach a log, a trace, or a transcript through
    # repr(config). Any code that stringifies a whole context object — a debug print, a
    # trace fallback that reprs an unknown value — would otherwise carry the key with
    # it. Tool arguments are built explicitly for the same reason; this is the layer
    # that holds if that discipline ever slips.
    api_key: str | None = field(default=None, repr=False)
    prompts_dir: Path = REPO_ROOT / DEFAULT_PROMPTS_DIR
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def artifact_path(self, subagent: str) -> Path | None:
        """The compiled artifact for one specialist, or None when it has no target.

        A specialist with no entry in COMPILED_ARTIFACTS is hand-written by decision,
        not by accident. ADR-012 holds the test that decides which ones qualify.
        """
        filename = COMPILED_ARTIFACTS.get(subagent)
        return None if filename is None else self.prompts_dir / filename

    def has_artifact(self, subagent: str) -> bool:
        path = self.artifact_path(subagent)
        return path is not None and path.is_file()

    def require_key(self) -> str:
        """Return the key, or raise with the variable name to set."""
        if not self.api_key:
            raise RuntimeError(
                f"{KEY_VAR} is not set. Ray needs it to reach the model. "
                f"Copy .env.example to .env and fill it in, or export {KEY_VAR}."
            )
        return self.api_key


def load_config(env: dict[str, str] | None = None) -> Config:
    """Build the configuration from the environment.

    Passing `env` makes this testable without touching the real environment.
    """
    src = os.environ if env is None else env

    def get(name: str, default: str) -> str:
        # An empty string counts as unset, so that `RAY_PORT=` falls back.
        return (src.get(name) or "").strip() or default

    key = (src.get(KEY_VAR) or "").strip()

    return Config(
        db_path=_resolve(get("RAY_DB_PATH", DEFAULT_DB_PATH)),
        model=get("RAY_MODEL", DEFAULT_MODEL),
        api_key=key or None,
        prompts_dir=_resolve(get("RAY_PROMPTS_DIR", DEFAULT_PROMPTS_DIR)),
        host=get("RAY_HOST", DEFAULT_HOST),
        port=int(get("RAY_PORT", str(DEFAULT_PORT))),
    )
