from __future__ import annotations

import asyncio
import json
import re
import shutil

from ..models import Edge, Node, Snapshot

PING_RE = re.compile(r"in ([0-9.]+)ms")


class TailscaleCliProvider:
    """Читает `tailscale status --json` — единственный источник, который знает,
    идёт ли трафик напрямую или через DERP-реле.
    """

    name = "tailscale"

    def __init__(self, binary: str | None = None, probe_rtt: bool = False) -> None:
        self.binary = binary or shutil.which("tailscale") or "tailscale"
        self.probe_rtt = probe_rtt

    async def fetch(self) -> Snapshot:
        proc = await asyncio.create_subprocess_exec(
            self.binary,
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        raw, err = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"tailscale status failed: {err.decode(errors='replace')[:300]}")
        snapshot = self.parse(json.loads(raw.decode("utf-8")))
        if self.probe_rtt:
            snapshot = await _probe(snapshot, self.binary)
        return snapshot

    def parse(self, data: dict) -> Snapshot:
        nodes: dict[str, Node] = {}
        edges: list[Edge] = []

        self_node = data.get("Self") or {}
        self_id: str | None = None
        if self_node:
            node = _to_node(self_node, fallback="self")
            node.is_self = True
            nodes[node.id] = node
            self_id = node.id

        # В новых версиях Tailscale ключ называется Peer, в старых — Peers.
        peers: dict = data.get("Peers") or data.get("Peer") or {}
        for key, raw in peers.items():
            node = _to_node(raw, fallback=str(key))
            nodes[node.id] = node

        self_id = self_id or next(iter(nodes), None)
        for key, raw in peers.items():
            node = nodes.get(_node_id(raw, str(key)))
            if node is None or node.id == self_id:
                continue
            cur_addr = (raw.get("CurAddr") or "").strip()
            relay = raw.get("Relay") or None
            edges.append(
                Edge(
                    src=self_id or node.id,
                    dst=node.id,
                    path="direct" if cur_addr else ("relay" if relay else "unknown"),
                    relay=relay,
                    rx_bytes=int(raw.get("RxBytes") or 0),
                    tx_bytes=int(raw.get("TxBytes") or 0),
                )
            )

        return Snapshot(nodes=nodes, edges=edges, provider=self.name, self_id=self_id)


def _node_id(raw: dict, fallback: str = "node") -> str:
    return str(raw.get("ID") or raw.get("DNSName") or raw.get("HostName") or fallback)


def _to_node(raw: dict, fallback: str = "node") -> Node:
    tags = [t.replace("tag:", "") for t in (raw.get("Tags") or [])]
    ips = list(raw.get("TailscaleIPs") or [])
    return Node(
        id=_node_id(raw, fallback),
        hostname=str(raw.get("HostName") or raw.get("DNSName") or "node").split(".")[0],
        os=str(raw.get("OS") or "linux"),
        online=bool(raw.get("Online", True)),
        tags=tags,
        exit_node=bool(raw.get("ExitNode") or raw.get("ExitNodeOption")),
        ips=ips,
        rx_bytes=int(raw.get("RxBytes") or 0),
        tx_bytes=int(raw.get("TxBytes") or 0),
    )


async def _probe(snapshot: Snapshot, binary: str) -> Snapshot:
    """RTT через `tailscale ping`: единственный способ узнать реальную задержку.

    Осторожно: ping прогревает путь и может перевести пира с DERP на прямой,
    поэтому по умолчанию выключен.
    """
    for edge in snapshot.edges:
        node = snapshot.nodes.get(edge.dst)
        if not node or not node.online or not node.primary_ip:
            continue
        proc = await asyncio.create_subprocess_exec(
            binary,
            "ping",
            "-c",
            "1",
            "--timeout",
            "2s",
            node.primary_ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        match = PING_RE.search(out.decode(errors="replace"))
        if match:
            edge.rtt_ms = round(float(match.group(1)), 1)
    return snapshot
