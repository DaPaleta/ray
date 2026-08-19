"""Environment variables and defaults.

This module holds every default. No other module reads os.environ.
See docs/decisions/ADR-005-model-boundary-and-offline-testability.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# The repository root, resolved from this file: src/ray/config.py -> ray/
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_DB_PATH = "data/ocean_home_task.db"
DEFAULT_COMPILED_PROMPT = "prompts/adjudicator.compiled.json"
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
    api_key: str | None
    compiled_prompt_path: Path
    host: str
    port: int

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def has_compiled_prompt(self) -> bool:
        return self.compiled_prompt_path.is_file()

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
        compiled_prompt_path=_resolve(
            get("RAY_COMPILED_PROMPT", DEFAULT_COMPILED_PROMPT)
        ),
        host=get("RAY_HOST", DEFAULT_HOST),
        port=int(get("RAY_PORT", str(DEFAULT_PORT))),
    )
