"""The trace must always survive JSON serialization.

The portal returns `Turn.to_dict()` straight to the browser. A single unserializable
value anywhere in a trace turns a good answer into a 500 and shows the analyst
`SyntaxError: Unexpected token 'I', "Internal S"... is not valid JSON`.

That happened for real. `find_messages`, `find_users`, and `recall` recorded their
arguments with `locals()`. Inside a closure, `locals()` also returns the free
variables the function references, so `ctx` — and with it a `sqlite3.Connection` —
landed in the tool-call log. The portal tests passed anyway, because they used a fake
Ray whose tools recorded nothing.

These tests close both halves: the trace tolerates any value, and the real tool
wrappers record only scalars.
"""

from __future__ import annotations

import json
import sqlite3

from ray import schemas, subagents, trace
from ray.config import load_config


# --- json_safe tolerates anything ---------------------------------------------


def test_json_safe_passes_scalars_through():
    assert trace.json_safe({"a": 1, "b": "x", "c": None, "d": True, "e": 1.5}) == {
        "a": 1,
        "b": "x",
        "c": None,
        "d": True,
        "e": 1.5,
    }


def test_json_safe_degrades_an_unserializable_value(cfg):
    conn = sqlite3.connect(":memory:")
    try:
        result = trace.json_safe({"conn": conn})
        assert isinstance(result["conn"], str)
        json.dumps(result)  # must not raise
    finally:
        conn.close()


def test_json_safe_handles_nesting_and_sequences():
    payload = {"rows": [{"n": 1}, {"n": 2}], "tags": ("a", "b"), "set": {"z"}}
    out = trace.json_safe(payload)
    assert out["rows"] == [{"n": 1}, {"n": 2}]
    assert out["tags"] == ["a", "b"]
    json.dumps(out)


def test_json_safe_stops_at_a_depth_limit():
    deep: dict = {}
    node = deep
    for _ in range(30):
        node["next"] = {}
        node = node["next"]
    json.dumps(trace.json_safe(deep))  # must not recurse without bound


# --- a turn holding a connection still serializes ------------------------------


def test_turn_with_a_connection_in_its_arguments_still_serializes():
    """The exact shape of the bug that reached the browser."""
    conn = sqlite3.connect(":memory:")
    try:
        turn = trace.Turn(question="q", model="m")
        turn.record("find_messages", {"department": "finance", "ctx": conn})
        turn.answer = "an answer"
        json.dumps(turn.to_dict())  # must not raise
    finally:
        conn.close()


def test_turn_to_dict_is_always_json_serializable():
    turn = trace.Turn(question="q", model="m")
    result = schemas.ToolResult(
        text="rows",
        data={"nodes": [{"id": "msg:1", "kind": "message"}], "edges": []},
        citations=[schemas.cite("msg", "93bae03bfd4b5d7bac960ab6cc8dab41")],
        injection_findings=[{"pattern": "role-marker", "evidence": "system:"}],
        window="a window",
    )
    turn.record("entity_graph", {"indicator": "x", "depth": 1}, result)
    turn.answer = "answer"
    turn.grounding = {"ok": True, "citation_count": 1, "failures": []}
    payload = json.loads(json.dumps(turn.to_dict()))
    assert payload["graph"]["nodes"][0]["id"] == "msg:1"
    assert payload["tool_calls"][0]["window"] == "a window"


# --- the real tool wrappers record only scalars --------------------------------


def test_no_tool_records_a_connection_in_its_arguments(conn):
    """Drive every registered tool and assert the trace stays serializable.

    This is the test that would have caught the original defect. It calls the real
    wrappers from `subagents.build_tools`, which is where `locals()` leaked `ctx`.
    """
    cfg = load_config(env={})
    session = trace.Session(model="test")
    ctx = subagents.RayContext(cfg=cfg, conn=conn, session=session)
    registry = subagents.build_tools(ctx)
    turn = session.start("drive every tool")

    invocations: dict[str, dict] = {
        "find_messages": {"department": "finance", "flagged_only": True, "limit": 5},
        "get_message": {"message_id": "93bae03b"},
        "get_message_body": {"message_id": "93bae03b"},
        "get_detection": {"message_id": "93bae03b"},
        "domain_intel": {"domain": "login-verify.acme-portal.co"},
        "entity_graph": {"indicator": "login-verify.acme-portal.co", "depth": 1},
        "find_users": {"department": "finance", "limit": 5},
        "blast_radius": {"indicator": "login-verify.acme-portal.co"},
        "recall": {},
        "watchlist_sweep": {},
    }
    assert set(invocations) <= set(registry), "a registered tool is untested here"

    for name, arguments in invocations.items():
        registry[name].invoke(arguments)

    assert len(turn.calls) == len(invocations)
    for call in turn.calls:
        for key, value in call.arguments.items():
            assert isinstance(
                value, (str, int, float, bool, type(None))
            ), f"{call.name} recorded a non-scalar argument {key}={value!r}"

    json.dumps(turn.to_dict())  # the portal path


def test_every_registered_tool_is_covered_by_the_serialization_test(conn):
    """Guard against a new tool escaping the check above."""
    cfg = load_config(env={})
    ctx = subagents.RayContext(cfg=cfg, conn=conn, session=trace.Session())
    registry = subagents.build_tools(ctx)
    # `remember` is exercised in test_memory.py, which covers its provenance rules.
    expected = {
        "find_messages",
        "get_message",
        "get_message_body",
        "get_detection",
        "domain_intel",
        "entity_graph",
        "find_users",
        "blast_radius",
        "recall",
        "remember",
        "watchlist_sweep",
    }
    assert set(registry) == expected, (
        "The tool registry changed. Add the new tool to "
        "test_no_tool_records_a_connection_in_its_arguments."
    )
