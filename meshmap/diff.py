from __future__ import annotations

import time

from .models import Snapshot


def diff(prev: Snapshot | None, cur: Snapshot, ts: float | None = None) -> list[dict]:
    """Сравнивает два снапшота и возвращает человекочитаемые события."""
    ts = ts if ts is not None else time.time()
    events: list[dict] = []
    if prev is None:
        events.append(
            {
                "ts": ts,
                "kind": "info",
                "node": None,
                "message": f"топология загружена: {len(cur.nodes)} узлов, {len(cur.edges)} связей",
            }
        )
        return events

    for node_id, node in cur.nodes.items():
        old = prev.nodes.get(node_id)
        if old is None:
            events.append(
                {
                    "ts": ts,
                    "kind": "node",
                    "node": node.hostname,
                    "message": f"новый узел: {node.hostname}",
                }
            )
        elif old.online != node.online:
            state = "снова онлайн" if node.online else "офлайн"
            events.append(
                {
                    "ts": ts,
                    "kind": "node" if node.online else "warn",
                    "node": node.hostname,
                    "message": f"{node.hostname} {state}",
                }
            )

    for node_id, node in prev.nodes.items():
        if node_id not in cur.nodes:
            events.append(
                {
                    "ts": ts,
                    "kind": "warn",
                    "node": node.hostname,
                    "message": f"узел пропал: {node.hostname}",
                }
            )

    prev_edges = {e.key: e for e in prev.edges}
    for edge in cur.edges:
        old = prev_edges.get(edge.key)
        if old is None:
            continue
        a = _name(cur, edge.src)
        b = _name(cur, edge.dst)
        if old.path != edge.path and {old.path, edge.path} <= {"direct", "relay"}:
            if edge.path == "relay":
                where = f" DERP {edge.relay}" if edge.relay else " DERP"
                message = f"{a} ↔ {b}: прямой → {where.strip()}"
            else:
                message = f"{a} ↔ {b}: DERP → прямой"
            events.append({"ts": ts, "kind": "path", "node": a, "message": message})
        if old.rtt_ms and edge.rtt_ms:
            grew = edge.rtt_ms > old.rtt_ms * 1.8 and edge.rtt_ms - old.rtt_ms > 15
            if grew:
                events.append(
                    {
                        "ts": ts,
                        "kind": "latency",
                        "node": a,
                        "message": f"{a} ↔ {b}: RTT {old.rtt_ms:.0f} → {edge.rtt_ms:.0f} мс",
                    }
                )

    return events


def _name(snapshot: Snapshot, node_id: str) -> str:
    node = snapshot.nodes.get(node_id)
    return node.hostname if node else node_id
