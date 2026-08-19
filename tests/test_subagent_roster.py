"""The five-specialist roster, its tool sets, and per-specialist prompt loading.

ADR-011 owns the roster. ADR-012 owns the per-specialist compiled artifact. No test
here calls a model, and none imports DSPy.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ray import config as config_module
from ray import prompts, subagents
from ray.config import Config

EXPECTED_ROSTER = {
    "triage-officer": ("find_messages", "get_detection", "watchlist_sweep", "recall"),
    "auth-forensics": ("get_message", "find_users", "domain_intel"),
    "campaign-correlator": ("find_messages", "domain_intel", "entity_graph"),
    "verdict-reviewer": ("get_detection", "get_message", "get_message_body", "recall"),
    "incident-responder": ("blast_radius", "get_detection", "find_users", "recall"),
}


@pytest.fixture()
def ctx(conn: sqlite3.Connection) -> subagents.RayContext:
    return subagents.RayContext(cfg=config_module.load_config(env={}), conn=conn)


def test_roster_holds_the_five_soc_roles(ctx):
    built = {spec["name"]: spec for spec in subagents.build_subagents(ctx)}
    assert set(built) == set(EXPECTED_ROSTER)


def test_each_specialist_reaches_only_its_own_tools(ctx):
    for spec in subagents.build_subagents(ctx):
        names = tuple(tool.name for tool in spec["tools"])
        assert set(names) == set(EXPECTED_ROSTER[spec["name"]]), spec["name"]


def test_only_the_reviewer_reaches_body_text(ctx):
    """A triage order and a response plan follow from recorded rows, not from prose."""
    assert subagents.NO_BODY_ACCESS == set(EXPECTED_ROSTER) - {"verdict-reviewer"}
    for spec in subagents.build_subagents(ctx):
        has_body = any(tool.name == "get_message_body" for tool in spec["tools"])
        assert has_body is (spec["name"] not in subagents.NO_BODY_ACCESS), spec["name"]


def test_body_access_is_refused_at_construction_not_only_in_a_test(ctx, monkeypatch):
    """ADR-011 states this as a safety property, so it fails loudly, not silently."""
    broken = dict(subagents.SUBAGENT_TOOLS)
    broken["triage-officer"] = (*broken["triage-officer"], "get_message_body")
    monkeypatch.setattr(subagents, "SUBAGENT_TOOLS", broken)
    with pytest.raises(ValueError, match="NO_BODY_ACCESS"):
        subagents.build_subagents(ctx)


def test_every_specialist_carries_the_citation_rules_and_the_case_note(ctx):
    for spec in subagents.build_subagents(ctx):
        assert "Citing evidence" in spec["system_prompt"], spec["name"]
        assert "SOC case note" in spec["system_prompt"], spec["name"]


def test_the_gated_roles_state_that_ray_never_acts(ctx):
    """docs/vision.md 4.2 item 3: Ray recommends, and Ray never remediates."""
    assert "Ray never acts" in prompts.INCIDENT_RESPONDER_PROMPT
    assert "never a feed" in prompts.TRIAGE_OFFICER_PROMPT


def test_system_prompt_routes_the_three_tiers():
    system = prompts.SYSTEM_PROMPT
    for name in EXPECTED_ROSTER:
        assert name in system, name
    # The response role is gated behind an established finding, and blast_radius
    # hands its facts on rather than prescribing (ADR-011).
    assert "gated" in system
    assert "blast_radius" in system


def test_compiled_prompt_replaces_only_its_own_specialist(ctx):
    compiled = {"campaign-correlator": "COMPILED CORRELATOR CORE"}
    built = {spec["name"]: spec["system_prompt"] for spec in subagents.build_subagents(ctx, compiled)}
    assert built["campaign-correlator"] == "COMPILED CORRELATOR CORE"
    assert built["verdict-reviewer"] == prompts.VERDICT_REVIEWER_PROMPT
    assert built["triage-officer"] == prompts.TRIAGE_OFFICER_PROMPT


def test_absent_artifacts_fall_back_without_raising(tmp_path):
    """An absent artifact is a supported state, not a crash (IR8)."""
    cfg = Config(db_path=tmp_path / "unused.db", model="m", prompts_dir=tmp_path)
    loaded, statuses = subagents.load_compiled_prompts(cfg)
    assert loaded == {}
    assert len(statuses) == len(EXPECTED_ROSTER)
    assert all("hand-written" in line for line in statuses)


def test_a_specialist_without_a_compile_target_says_so(tmp_path):
    cfg = Config(db_path=tmp_path / "unused.db", model="m", prompts_dir=tmp_path)
    statuses = {line.split(":")[0]: line for line in subagents.load_compiled_prompts(cfg)[1]}
    assert "no compile target" in statuses["triage-officer"]
    assert "no compile target" in statuses["incident-responder"]
    assert "no compile target" in statuses["auth-forensics"]
    # The two labelled specialists have a target, so their fallback names the artifact.
    assert "no artifact at" in statuses["verdict-reviewer"]
    assert "no artifact at" in statuses["campaign-correlator"]


def test_a_stored_core_is_wrapped_in_the_fixed_blocks_at_load_time(tmp_path):
    """An edit to the citation rules must reach a compiled prompt without a recompile."""
    cfg = Config(db_path=tmp_path / "unused.db", model="m", prompts_dir=tmp_path)
    path = cfg.artifact_path("campaign-correlator")
    path.write_text(
        json.dumps({"core": "CORE FROM DISK", "prompt": "STALE ASSEMBLY", "score": 0.5}),
        encoding="utf-8",
    )
    loaded, statuses = subagents.load_compiled_prompts(cfg)
    assert loaded["campaign-correlator"] == prompts.with_fixed_blocks("CORE FROM DISK")
    assert "STALE ASSEMBLY" not in loaded["campaign-correlator"]
    assert any("compiled from correlator.compiled.json (core" in line for line in statuses)


def test_an_artifact_without_a_core_falls_back_to_its_assembled_prompt(tmp_path):
    cfg = Config(db_path=tmp_path / "unused.db", model="m", prompts_dir=tmp_path)
    cfg.artifact_path("campaign-correlator").write_text(
        json.dumps({"prompt": "WHOLE PROMPT FROM DISK", "score": 0.5}), encoding="utf-8"
    )
    loaded, statuses = subagents.load_compiled_prompts(cfg)
    assert loaded == {"campaign-correlator": "WHOLE PROMPT FROM DISK"}
    assert any("(prompt, score" in line for line in statuses)


def test_a_broken_artifact_falls_back_instead_of_raising(tmp_path):
    cfg = Config(db_path=tmp_path / "unused.db", model="m", prompts_dir=tmp_path)
    cfg.artifact_path("verdict-reviewer").write_text("{not json", encoding="utf-8")
    cfg.artifact_path("campaign-correlator").write_text(json.dumps({"score": 1}), encoding="utf-8")
    loaded, statuses = subagents.load_compiled_prompts(cfg)
    assert loaded == {}
    joined = "\n".join(statuses)
    assert "could not read reviewer.compiled.json" in joined
    assert "holds no prompt" in joined


def test_committed_artifacts_load_for_the_real_configuration():
    """The committed artifacts are what a clean checkout runs (ADR-012 follow-up)."""
    cfg = config_module.load_config(env={})
    loaded, statuses = subagents.load_compiled_prompts(cfg)
    for name in ("verdict-reviewer", "campaign-correlator"):
        assert name in loaded, f"{name} artifact missing: {statuses}"
        assert "Citing evidence" in loaded[name], f"{name} lost its fixed blocks"


def test_fixed_blocks_are_appended_and_not_optimizable():
    """IR1 and IR4 do not bend to a metric (ADR-012)."""
    wrapped = prompts.with_fixed_blocks("CORE ONLY")
    assert wrapped.startswith("CORE ONLY")
    assert "Citing evidence" in wrapped
    assert "attacker-controlled" in wrapped
    assert "SOC case note" in wrapped
    assert "attacker-controlled" not in prompts.with_fixed_blocks("CORE", untrusted=False)
