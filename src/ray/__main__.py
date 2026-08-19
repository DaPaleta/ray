"""Entry point.

    python -m ray                     start the portal
    python -m ray --ask "question"    answer one question and write a transcript
    python -m ray --check             report readiness without calling the model

The one-shot mode exists so that the `transcripts/` deliverable is reproducible and
needs no web interface. plan.md section 5 puts it before the portal for that reason.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import subagents
from .agent import Ray
from .config import REPO_ROOT, load_config

TRANSCRIPT_DIR = REPO_ROOT / "transcripts"


def _slug(text: str, limit: int = 48) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text.strip()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:limit] or "question"


def _print_startup(ray: Ray, *, detail: bool = False) -> None:
    startup = ray.startup()
    for line in startup.notes:
        print(f"  {line}")
    if detail:
        # One line per specialist. The portal header shows only the summary, so the
        # readiness check is where an analyst sees which prompt each specialist runs.
        for line in startup.prompt_detail:
            print(f"    - {line}")


def command_check(ray: Ray) -> int:
    """Report readiness. Calls no model, so it works without a key."""
    print("Ray readiness check")
    _print_startup(ray, detail=True)
    print(f"  Tools registered: {len(ray.registry)} — {', '.join(sorted(ray.registry))}")
    print(f"  Specialists: {len(subagents.SUBAGENT_TOOLS)} — "
          f"{', '.join(subagents.SUBAGENT_TOOLS)}")
    if not ray.cfg.has_key:
        print("\n  NOT READY: set OCEAN_ANTHROPIC_KEY (see .env.example).")
        return 1
    print("\n  Ready.")
    return 0


def command_ask(ray: Ray, question: str, out: Path | None, index: int | None) -> int:
    print(f"\n> {question}\n")
    turn = ray.ask(question)

    if turn.error:
        print(f"ERROR: {turn.error}", file=sys.stderr)
    print(turn.answer or "(no answer)")

    grounding = turn.grounding or {}
    if grounding:
        print(f"\n[grounding] {grounding.get('summary', '')}")
        for failure in grounding.get("failures", []):
            print(f"[grounding] FAILED citation: {failure}")
        if grounding.get("uncited_warning"):
            print(f"[grounding] {grounding['uncited_warning']}")

    for name in turn.subagents_used:
        count = sum(1 for c in turn.calls if c.subagent == name)
        print(f"[specialist] {name} took part — {count} tool call(s)")

    for finding in turn.all_injection_findings:
        print(f"[injection] {finding.get('pattern')}: {finding.get('evidence', '')}")

    for proposal in turn.memory_proposals:
        print(
            f"\n[memory] Ray proposes to remember ({proposal['kind']}): "
            f"{proposal['content']}\n"
            f"[memory] Confirm with: python -m ray --confirm {proposal['proposal_id']}"
        )

    target = out or (
        TRANSCRIPT_DIR / f"{index:02d}-{_slug(question)}.md" if index
        else TRANSCRIPT_DIR / f"{_slug(question)}.md"
    )
    ray.session.save_markdown(target)
    # A path outside the repository has no relative form, and `--out` accepts any
    # path. Report it absolutely rather than raising after the work is done.
    try:
        shown = target.relative_to(REPO_ROOT)
    except ValueError:
        shown = target
    print(f"\nTranscript written to {shown}")
    return 1 if turn.error else 0


def command_portal(ray: Ray) -> int:
    from .portal.app import serve

    print("Ray portal")
    _print_startup(ray)
    print(f"\n  Open http://{ray.cfg.host}:{ray.cfg.port}")
    print("  Keep the tab open; Ray holds the conversation across turns.\n")
    serve(ray)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ray",
        description="Ray — an email-threat investigator agent.",
    )
    parser.add_argument("--ask", metavar="QUESTION", help="answer one question, then exit")
    parser.add_argument("--out", metavar="PATH", help="where to write the transcript")
    parser.add_argument(
        "--index", type=int, help="number the transcript file, e.g. 01-..."
    )
    parser.add_argument(
        "--check", action="store_true", help="report readiness without calling the model"
    )
    parser.add_argument(
        "--confirm", metavar="PROPOSAL_ID", help="confirm a proposed memory record"
    )
    args = parser.parse_args(argv)

    ray = Ray(load_config())
    try:
        if args.check:
            return command_check(ray)
        if args.confirm:
            memory_id = ray.confirm_memory(args.confirm)
            print(f"Stored memory record {memory_id}.")
            return 0
        if args.ask:
            return command_ask(
                ray, args.ask, Path(args.out) if args.out else None, args.index
            )
        return command_portal(ray)
    finally:
        ray.close()


if __name__ == "__main__":
    raise SystemExit(main())
