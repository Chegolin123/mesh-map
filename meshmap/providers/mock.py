from __future__ import annotations

import math
import random

from ..models import Edge, Node, Snapshot, SshInfo

# (id, hostname, os, tags, exit_node, rx_gb, tx_gb)
NODES = [
    ("desktop", "home-pc", "windows", ["exit-node"], True, 41.2, 18.4),
    ("server", "home-server", "linux", [], False, 88.7, 122.9),
    ("vps-ru", "vps-ru", "linux", ["prod"], False, 64.1, 51.3),
    ("vps-ams", "vps-ams", "linux", ["eu"], False, 39.5, 44.8),
    ("macbook", "macbook-air", "macos", [], False, 12.8, 9.1),
    ("phone", "pixel-8", "android", [], False, 3.4, 2.2),
    ("nas", "nas-4tb", "linux", ["backup"], False, 21.6, 30.5),
]

IPS = {
    "desktop": "100.101.1.10",
    "server": "100.101.1.20",
    "vps-ru": "100.101.1.30",
    "vps-ams": "100.101.1.40",
    "macbook": "100.101.1.50",
    "phone": "100.101.1.60",
    "nas": "100.101.1.70",
}

# node_id → (state, banner, rtt)
SSH = {
    "desktop": ("open", "OpenSSH_for_Windows_9.5", 2.8),
    "server": ("open", "OpenSSH_9.6p1", 1.4),
    "vps-ru": ("open", "OpenSSH_8.9p1", 14.2),
    "vps-ams": ("open", "OpenSSH_9.2p1", 39.6),
    "macbook": ("open", "OpenSSH_9.8", 7.9),
    "phone": ("closed", None, None),
    "nas": ("open", "dropbear_2022.83", 1.1),
}

# (src, dst, path, relay, base_rtt, weight)
EDGES = [
    ("desktop", "server", "direct", None, 2.4, 4.0),
    ("desktop", "macbook", "direct", None, 8.1, 1.6),
    ("server", "vps-ru", "direct", None, 14.0, 3.0),
    ("server", "nas", "direct", None, 1.1, 3.6),
    ("server", "phone", "relay", "ams", 62.0, 1.0),
    ("vps-ru", "vps-ams", "direct", None, 39.0, 2.4),
    ("macbook", "vps-ams", "direct", None, 27.0, 1.2),
]


class MockProvider:
    """Синтетическая, но правдоподобная сеть.

    Нужна для демо и для тестов: одинаковый seed + tick = одинаковый снапшот.
    Периодически портит один путь и один узел, чтобы было видно, как работают
    события и таймлайн.
    """

    name = "mock"

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.tick = 0

    async def fetch(self) -> Snapshot:
        self.tick += 1
        return self.snapshot(self.tick)

    def snapshot(self, tick: int) -> Snapshot:
        rng = random.Random(self.seed * 100_003 + tick)
        wobble = math.sin(tick / 3.0)

        degraded = 9 <= tick % 17 <= 11
        phone_offline = 19 <= tick % 23 <= 20

        nodes: dict[str, Node] = {}
        for node_id, hostname, os_name, tags, is_exit, rx, tx in NODES:
            online = True
            if node_id == "phone" and phone_offline:
                online = False
            ssh_state, banner, ssh_rtt = SSH[node_id]
            nodes[node_id] = Node(
                id=node_id,
                hostname=hostname,
                os=os_name,
                online=online,
                tags=list(tags),
                exit_node=is_exit,
                ips=[IPS[node_id]],
                rx_bytes=int((rx + rng.random() * 0.4) * 1e9),
                tx_bytes=int((tx + rng.random() * 0.3) * 1e9),
                ssh=(
                    SshInfo(
                        state=ssh_state if online else "closed",
                        banner=banner if online else None,
                        rtt_ms=ssh_rtt,
                    )
                    if ssh_state
                    else None
                ),
            )

        edges: list[Edge] = []
        for src, dst, path, relay, rtt, weight in EDGES:
            edge_path = path
            edge_relay = relay
            edge_rtt = rtt

            if (src, dst) == ("macbook", "vps-ams"):
                if degraded:
                    edge_path, edge_relay, edge_rtt = "relay", "fra", 138.0
                else:
                    edge_rtt = rtt + wobble * 1.5

            jitter = rng.uniform(-0.6, 0.6)
            edges.append(
                Edge(
                    src=src,
                    dst=dst,
                    path=edge_path,  # type: ignore[arg-type]
                    relay=edge_relay,
                    rtt_ms=round(max(0.4, edge_rtt + jitter), 1),
                    rx_bytes=int(weight * 1e8 + rng.random() * 5e7),
                    tx_bytes=int(weight * 7e7 + rng.random() * 4e7),
                )
            )

        return Snapshot(nodes=nodes, edges=edges, provider=self.name)
