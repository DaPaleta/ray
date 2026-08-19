"""Domain intelligence and the entity graph.

Two tools live here. Both join on a shared indicator, never on `campaign_id`
alone (plan.md 8, query trap 1): a `campaign_id` join returns 14 messages on the
acme-portal domain where 15 is correct, because message `93bae03b` carries an
empty `campaign_id`.

`domain_intel` reports everything the corpus knows about one domain, from both
directions: as a link domain and as a sender domain (plan.md 4.4 tool 5).

`entity_graph` builds a graph of nodes and edges around one indicator, by
breadth-first expansion over the shared-indicator relationships (plan.md 4.4
tool 6). It is the most important tool in this stage: it is how the
campaign-correlator subagent finds `93bae03b` despite its empty `campaign_id`,
and it is the data the portal renders as a graph.
"""

from __future__ import annotations

import difflib
import re
import sqlite3
from collections import Counter

from .. import db, schemas


def _sender_domain_expr(column: str = "sender_email") -> str:
    """The expression that pulls the domain half out of a sender address.

    SQLite has no split() function, so this is the portable form. `column`
    lets a caller qualify it with a table alias, e.g. `m.sender_email`.
    """
    return f"substr({column}, instr({column}, '@') + 1)"


# Message ids in this corpus are 32-character hex hashes. Ray shows the first 8
# (schemas.SHORT_ID_LEN), so a lookup accepts either length.
_HEX32_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)
_HEX8_RE = re.compile(r"^[0-9a-f]{8}$", re.IGNORECASE)
_DOMAIN_SHAPE_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$",
    re.IGNORECASE,
)

# Node kinds the portal understands. entity_graph never emits any other kind.
_NODE_KINDS = {"message", "user", "domain", "campaign", "sender"}


def _domain_match_clause(expr: str) -> str:
    """A domain matches when it equals the query, is a subdomain of it, or the
    query is a subdomain of it. `acme-portal.co` therefore matches
    `login-verify.acme-portal.co` and `mail.acme-portal.co`, in either direction.

    Uses the named parameters `:d` (the lowercased query) and `:d_sub`
    (`%.` + the lowercased query). Callers must supply both.
    """
    return f"(LOWER({expr}) = :d OR LOWER({expr}) LIKE :d_sub OR :d LIKE ('%.' || LOWER({expr})))"


def _looks_like_lookalike(candidate: str, primary: str) -> bool:
    """True when `candidate` trades on the organization's brand but is not
    `primary`. Scenario 4 depends on this: `acme-robotics.com` is not
    `acme.com`, and a passing SPF/DKIM/DMARC on that domain proves nothing about
    the sender's legitimacy — it only proves the attacker configured their own
    domain correctly.
    """
    if candidate == primary:
        return False
    primary_root = primary.split(".")[0]
    if primary_root and primary_root in candidate:
        return True
    return difflib.SequenceMatcher(None, candidate, primary).ratio() >= 0.6


# ---------------------------------------------------------------------------
# domain_intel
# ---------------------------------------------------------------------------


def domain_intel(conn: sqlite3.Connection, domain: str) -> schemas.ToolResult:
    """Everything the corpus knows about one domain, as a link domain and as a
    sender domain, with subdomain matching in both directions.
    """
    domain_norm = (domain or "").strip().lower().lstrip(".")
    if not domain_norm:
        return schemas.ToolResult(
            text=schemas.unknown("domain intel", "No domain was given."),
            is_unknown=True,
        )

    params = {"d": domain_norm, "d_sub": f"%.{domain_norm}"}
    link_clause = _domain_match_clause("l.domain")
    sender_clause = _domain_match_clause(_sender_domain_expr("m.sender_email"))

    link_rows = db.rows(
        conn,
        f"""
        SELECT l.message_id, l.url, l.domain, l.is_scanned, l.scan_verdict,
               m.received_at
        FROM links l JOIN messages m ON m.message_id = l.message_id
        WHERE {link_clause}
        ORDER BY m.received_at
        """,
        params,
    )
    sender_rows = db.rows(
        conn,
        f"""
        SELECT m.message_id, m.received_at, m.sender_email, m.spf, m.dkim, m.dmarc
        FROM messages m
        WHERE {sender_clause}
        ORDER BY m.received_at
        """,
        params,
    )

    if not link_rows and not sender_rows:
        return schemas.ToolResult(
            text=schemas.unknown(
                f"domain {domain_norm}",
                "No link and no sender address in this corpus matches this domain, "
                "including as a subdomain.",
            ),
            is_unknown=True,
            data={"domain": domain_norm},
        )

    citations: list[str] = []
    lines = [f"Domain intel for {domain_norm}:"]

    # --- as a link domain ---
    link_message_ids = {r["message_id"] for r in link_rows}
    if link_rows:
        verdict_counts: Counter[str] = Counter()
        unscanned: list[str] = []
        unresolved: list[str] = []
        for r in link_rows:
            citations.append(schemas.cite("link", r["message_id"]))
            if r["is_scanned"] == 0:
                unscanned.append(r["message_id"])
                continue
            if r["scan_verdict"] == "unresolved":
                unresolved.append(r["message_id"])
            verdict_counts[r["scan_verdict"] or "(no verdict)"] += 1
        lines.append(
            f"- As a link domain: {len(link_rows)} link rows across "
            f"{len(link_message_ids)} messages."
        )
        for verdict, count in verdict_counts.most_common():
            lines.append(f"    scan_verdict={verdict}: {count}")
        if unscanned:
            lines.append(
                f"    is_scanned=0, no verdict recorded (NOT benign, IR10): "
                f"{len(unscanned)} — " + ", ".join(schemas.short(m) for m in unscanned)
            )
        if unresolved:
            lines.append(
                f"    scan_verdict=unresolved (NOT benign, IR10): {len(unresolved)} — "
                + ", ".join(schemas.short(m) for m in unresolved)
            )
    else:
        lines.append("- As a link domain: no rows.")

    # --- as a sender domain ---
    sender_message_ids = {r["message_id"] for r in sender_rows}
    if sender_rows:
        auth_counts: Counter[tuple[str | None, str | None, str | None]] = Counter()
        for r in sender_rows:
            citations.append(schemas.cite("msg", r["message_id"]))
            auth_counts[(r["spf"], r["dkim"], r["dmarc"])] += 1
        lines.append(f"- As a sender domain: {len(sender_rows)} messages.")
        for (spf, dkim, dmarc), count in auth_counts.most_common():
            lines.append(f"    spf={spf} dkim={dkim} dmarc={dmarc}: {count}")
    else:
        lines.append("- As a sender domain: no rows.")

    all_message_ids = link_message_ids | sender_message_ids

    all_received = [r["received_at"] for r in link_rows] + [
        r["received_at"] for r in sender_rows
    ]
    if all_received:
        lines.append(
            f"- First appearance: {min(all_received)}. Last appearance: {max(all_received)}."
        )

    if all_message_ids:
        placeholders = ",".join("?" * len(all_message_ids))
        id_params = tuple(all_message_ids)

        recipient_rows = db.rows(
            conn,
            f"""
            SELECT DISTINCT m.recipient_user_id, u.department, u.is_vip, u.display_name
            FROM messages m JOIN users u ON u.user_id = m.recipient_user_id
            WHERE m.message_id IN ({placeholders})
            """,
            id_params,
        )
        departments = sorted({r["department"] for r in recipient_rows})
        vip_hits = [r for r in recipient_rows if r["is_vip"]]
        lines.append(
            f"- Recipients reached: {len(recipient_rows)} distinct users across "
            f"{len(departments)} departments ({', '.join(departments)})."
        )
        if vip_hits:
            names = ", ".join(f"{r['display_name']} ({r['department']})" for r in vip_hits)
            lines.append(f"    VIP recipients hit: {len(vip_hits)} — {names}")
        else:
            lines.append("    No VIP recipient was reached.")

        campaign_rows = db.rows(
            conn,
            f"""
            SELECT campaign_id, count(*) c FROM messages
            WHERE message_id IN ({placeholders})
              AND campaign_id IS NOT NULL AND campaign_id != ''
            GROUP BY campaign_id
            """,
            id_params,
        )
        if campaign_rows:
            for r in campaign_rows:
                lines.append(
                    f"    campaign {r['campaign_id']}: {r['c']} of "
                    f"{len(all_message_ids)} messages carry this campaign_id "
                    "(a message can belong to this activity through a shared "
                    "indicator even when its own campaign_id is empty)"
                )
        else:
            lines.append("    No message on this domain carries a campaign_id.")

        decision_rows = db.rows(
            conn,
            f"SELECT message_id, verdict, attack_type FROM decisions "
            f"WHERE message_id IN ({placeholders})",
            id_params,
        )
        verdict_spread: Counter[str] = Counter()
        for r in decision_rows:
            citations.append(schemas.cite("decision", r["message_id"]))
            key = r["verdict"] + (f"/{r['attack_type']}" if r["attack_type"] else "")
            verdict_spread[key] += 1
        if verdict_spread:
            lines.append(
                "- Decision verdict spread: "
                + ", ".join(f"{k}: {v}" for k, v in verdict_spread.most_common())
            )

        remediation_rows = db.rows(
            conn,
            f"SELECT message_id, action FROM remediations WHERE message_id IN ({placeholders})",
            id_params,
        )
        remediation_counts = Counter(r["action"] for r in remediation_rows)
        missing_remediation = len(all_message_ids) - len(remediation_rows)
        remediation_bits = [f"{a}: {c}" for a, c in remediation_counts.most_common()]
        if missing_remediation:
            remediation_bits.append(f"no recorded remediation: {missing_remediation}")
        lines.append("- Remediation state: " + ", ".join(remediation_bits))
        for r in remediation_rows:
            citations.append(schemas.cite("remediation", r["message_id"]))

        overridden_rows = db.rows(
            conn,
            f"""
            SELECT message_id, overridden_by, override_reason FROM decisions
            WHERE message_id IN ({placeholders})
              AND overridden_by IS NOT NULL AND overridden_by != ''
            """,
            id_params,
        )
        if overridden_rows:
            by = Counter(r["overridden_by"] for r in overridden_rows)
            lines.append(
                f"- {len(overridden_rows)} decision(s) hold an override, by "
                + ", ".join(f"{who}: {n}" for who, n in by.most_common())
            )

    primary = db.primary_domain(conn)
    primary_lower = primary.lower()
    is_own_domain = domain_norm == primary_lower
    is_lookalike = (not is_own_domain) and _looks_like_lookalike(domain_norm, primary_lower)
    if is_own_domain:
        lines.append(f"- This IS the organization's own primary domain ({primary}).")
    elif is_lookalike:
        lines.append(
            f"- LOOKALIKE WARNING: {domain_norm} resembles the organization's primary "
            f"domain {primary} but is NOT it. A passing SPF/DKIM/DMARC result on this "
            "domain is not reassurance — it only proves the attacker's own domain is "
            "configured correctly, not that the sender is who it claims to be."
        )

    return schemas.ToolResult(
        text="\n".join(lines),
        data={
            "domain": domain_norm,
            "link_row_count": len(link_rows),
            "sender_message_count": len(sender_rows),
            "message_count": len(all_message_ids),
            "is_own_domain": is_own_domain,
            "is_lookalike": is_lookalike,
            "primary_domain": primary,
        },
        citations=citations,
    )


# ---------------------------------------------------------------------------
# entity_graph
# ---------------------------------------------------------------------------


def _resolve_indicator(
    conn: sqlite3.Connection, indicator: str
) -> tuple[str | None, str | None, str]:
    """Classify free text as a message, campaign, sender, domain, or subject.

    Returns (kind, canonical_value, note). `kind` is None when nothing in the
    corpus matches the text under any interpretation.
    """
    text = (indicator or "").strip()
    if not text:
        return None, None, "An empty indicator was given."

    if _HEX32_RE.match(text) or _HEX8_RE.match(text):
        row = db.one(conn, "SELECT message_id FROM messages WHERE message_id = ?", (text,))
        if not row and _HEX8_RE.match(text):
            candidates = db.rows(
                conn, "SELECT message_id FROM messages WHERE message_id LIKE ?", (f"{text}%",)
            )
            if len(candidates) == 1:
                row = candidates[0]
            elif len(candidates) > 1:
                return (
                    None,
                    None,
                    f"'{text}' matches {len(candidates)} message ids as a prefix; "
                    "ambiguous, give the full id.",
                )
        if row:
            mid = row["message_id"]
            return "message", mid, f"resolved '{text}' to message {schemas.short(mid)}"

    campaign_hit = db.one(
        conn, "SELECT 1 FROM messages WHERE campaign_id = ? LIMIT 1", (text,)
    )
    if campaign_hit:
        return "campaign", text, f"resolved '{text}' to campaign {text}"

    if "@" in text:
        sender_hit = db.one(
            conn, "SELECT 1 FROM messages WHERE LOWER(sender_email) = ? LIMIT 1", (text.lower(),)
        )
        if sender_hit:
            return "sender", text.lower(), f"resolved '{text}' to sender {text.lower()}"

    if "@" not in text and _DOMAIN_SHAPE_RE.match(text):
        domain_lower = text.lower()
        params = {"d": domain_lower, "d_sub": f"%.{domain_lower}"}
        link_hit = db.one(
            conn, f"SELECT 1 FROM links WHERE {_domain_match_clause('domain')} LIMIT 1", params
        )
        sender_hit = link_hit or db.one(
            conn,
            f"SELECT 1 FROM messages WHERE {_domain_match_clause(_sender_domain_expr())} LIMIT 1",
            params,
        )
        if link_hit or sender_hit:
            return "domain", domain_lower, f"resolved '{text}' to domain {domain_lower}"

    subject_hit = db.one(
        conn, "SELECT 1 FROM messages WHERE LOWER(subject) LIKE ? LIMIT 1", (f"%{text.lower()}%",)
    )
    if subject_hit:
        return "subject", text, f"resolved '{text}' as a subject match"

    return None, None, f"'{text}' matches no message, campaign, sender, domain, or subject."


def _expand_message(conn: sqlite3.Connection, mid: str) -> list[tuple[str, str, str, str]]:
    """One hop out of a message: its recipient, its link domain(s), its sender
    domain, and its campaign when non-empty. Returns
    (target_id, target_kind, target_value, relation).
    """
    out: list[tuple[str, str, str, str]] = []
    m = db.one(conn, "SELECT * FROM messages WHERE message_id = ?", (mid,))
    if not m:
        return out
    if m["recipient_user_id"]:
        out.append((f"user:{m['recipient_user_id']}", "user", m["recipient_user_id"], "sent_to"))
    for link in db.rows(conn, "SELECT DISTINCT domain FROM links WHERE message_id = ?", (mid,)):
        dom = link["domain"].lower()
        out.append((f"domain:{dom}", "domain", dom, "links_to"))
    sender_email = m["sender_email"] or ""
    if "@" in sender_email:
        sdom = sender_email.split("@", 1)[1].lower()
        out.append((f"domain:{sdom}", "domain", sdom, "sent_from"))
    if m["campaign_id"]:
        out.append((f"campaign:{m['campaign_id']}", "campaign", m["campaign_id"], "member_of"))
    return out


def _expand_hub(conn: sqlite3.Connection, kind: str, value: str) -> list[tuple[str, str]]:
    """One hop out of a domain, campaign, or sender hub, back to its messages.

    Returns (message_id, relation). A domain hub matches as a link domain and as
    a sender domain, with subdomain matching in both directions (the fix for
    query trap 1: this never joins on `campaign_id`).
    """
    if kind == "domain":
        params = {"d": value, "d_sub": f"%.{value}"}
        out = [
            (r["message_id"], "links_to")
            for r in db.rows(
                conn,
                f"SELECT DISTINCT message_id FROM links WHERE {_domain_match_clause('domain')}",
                params,
            )
        ]
        out += [
            (r["message_id"], "sent_from")
            for r in db.rows(
                conn,
                f"SELECT message_id FROM messages WHERE "
                f"{_domain_match_clause(_sender_domain_expr())}",
                params,
            )
        ]
        return out
    if kind == "campaign":
        return [
            (r["message_id"], "member_of")
            for r in db.rows(conn, "SELECT message_id FROM messages WHERE campaign_id = ?", (value,))
        ]
    if kind == "sender":
        return [
            (r["message_id"], "same_sender")
            for r in db.rows(
                conn, "SELECT message_id FROM messages WHERE LOWER(sender_email) = ?", (value,)
            )
        ]
    return []  # "user" is a leaf: never expand into every message a user received.


def entity_graph(
    conn: sqlite3.Connection, indicator: str, depth: int = 1, limit: int = 60
) -> schemas.ToolResult:
    """A graph of nodes and edges around one indicator.

    `indicator` is free text: a domain, a sender email, a message id (full or
    8-character prefix), a campaign id, or a subject. This never joins on
    `campaign_id` alone (query trap 1): a domain or sender hub is expanded
    through the shared indicator, so message `93bae03b` — empty `campaign_id` —
    still surfaces through its shared link domain with the other 14 campaign
    members.
    """
    kind, value, note = _resolve_indicator(conn, indicator)
    if kind is None:
        return schemas.ToolResult(
            text=schemas.unknown(f"entity graph for '{indicator}'", note),
            is_unknown=True,
            data={"nodes": [], "edges": []},
        )

    depth = max(1, int(depth))
    limit = max(1, int(limit))

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    edge_seen: set[tuple[str, str, str]] = set()
    cap_hit = False

    def add_node(node_id: str, node_kind: str, label: str) -> bool:
        nonlocal cap_hit
        if node_id in nodes:
            return True
        if len(nodes) >= limit:
            cap_hit = True
            return False
        assert node_kind in _NODE_KINDS, f"invalid node kind {node_kind!r}"
        nodes[node_id] = {"id": node_id, "kind": node_kind, "label": label}
        return True

    def add_edge(msg_id: str, hub_id: str, relation: str) -> None:
        source = f"msg:{msg_id}"
        key = (source, hub_id, relation)
        if key in edge_seen or source not in nodes or hub_id not in nodes:
            return
        edge_seen.add(key)
        edges.append({"source": source, "target": hub_id, "relation": relation})

    frontier_messages: list[str] = []
    frontier_hubs: list[tuple[str, str]] = []
    hops_done = 0

    if kind == "subject":
        matches = db.rows(
            conn,
            "SELECT message_id FROM messages WHERE LOWER(subject) LIKE ? ORDER BY received_at",
            (f"%{value.lower()}%",),
        )
        for r in matches:
            mid = r["message_id"]
            if add_node(f"msg:{mid}", "message", schemas.short(mid)):
                frontier_messages.append(mid)
        hops_done = 1  # the subject match is itself the direct neighbourhood.
    elif kind == "message":
        add_node(f"msg:{value}", "message", schemas.short(value))
        frontier_messages = [value]
    else:
        hub_id = f"{kind}:{value}"
        add_node(hub_id, kind, value)
        frontier_hubs = [(kind, value)]

    while (frontier_messages or frontier_hubs) and hops_done < depth and len(nodes) < limit:
        hops_done += 1
        next_messages: list[str] = []
        next_hubs: list[tuple[str, str]] = []

        for mid in frontier_messages:
            for target_id, target_kind, target_value, relation in _expand_message(conn, mid):
                label = schemas.short(target_value) if target_kind == "message" else target_value
                if add_node(target_id, target_kind, label):
                    add_edge(mid, target_id, relation)
                    if target_kind in ("domain", "campaign"):
                        next_hubs.append((target_kind, target_value))

        for hub_kind, hub_value in frontier_hubs:
            hub_id = f"{hub_kind}:{hub_value}"
            for mid, relation in _expand_hub(conn, hub_kind, hub_value):
                if add_node(f"msg:{mid}", "message", schemas.short(mid)):
                    add_edge(mid, hub_id, relation)
                    next_messages.append(mid)
                else:
                    add_edge(mid, hub_id, relation)

        frontier_messages = next_messages
        frontier_hubs = next_hubs

    citations = [
        schemas.cite("msg", n["id"].split(":", 1)[1]) for n in nodes.values() if n["kind"] == "message"
    ] + [
        schemas.cite("user", n["id"].split(":", 1)[1]) for n in nodes.values() if n["kind"] == "user"
    ]

    kind_counts = Counter(n["kind"] for n in nodes.values())
    relation_counts = Counter(e["relation"] for e in edges)
    lines = [
        f"Entity graph for '{indicator}': {note}",
        f"Resolved indicator kind: {kind}. Depth used: {hops_done} (requested {depth}).",
        f"Nodes: {len(nodes)} ("
        + ", ".join(f"{k}: {c}" for k, c in kind_counts.most_common())
        + f"). Edges: {len(edges)} ("
        + ", ".join(f"{r}: {c}" for r, c in relation_counts.most_common())
        + ").",
    ]
    if cap_hit:
        lines.append(f"Node cap of {limit} reached — this result is truncated.")
    notable = edges[:20]
    if notable:
        lines.append("Notable edges:")
        for e in notable:
            lines.append(f"  {e['source']} --{e['relation']}--> {e['target']}")
        if len(edges) > len(notable):
            lines.append(f"  ... and {len(edges) - len(notable)} more edges")

    return schemas.ToolResult(
        text="\n".join(lines),
        data={"nodes": list(nodes.values()), "edges": edges},
        citations=citations,
    )
