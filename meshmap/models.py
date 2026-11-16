from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

PathType = Literal["direct", "relay", "unknown"]

OS_LABELS = {
    "windows": "Windows",
    "linux": "Linux",
    "macos": "macOS",
    "darwin": "macOS",
    "ios": "iOS",
    "android": "Android",
    "freebsd": "FreeBSD",
}


@dataclass(slots=True)
class SshInfo:
    port: int = 22
    state: str = "unknown"  # open | closed | timeout | unknown
    banner: str | None = None
    rtt_ms: float | None = None

    @property
    def open(self) -> bool:
        return self.state == "open"

    def as_dict(self) -> dict:
        return {
            "port": self.port,
            "state": self.state,
            "open": self.open,
            "banner": self.banner,
            "rtt_ms": self.rtt_ms,
        }


@dataclass(slots=True)
class Node:
    id: str
    hostname: str
    os: str = "linux"
    online: bool = True
    tags: list[str] = field(default_factory=list)
    exit_node: bool = False
    ips: list[str] = field(default_factory=list)
    rx_bytes: int = 0
    tx_bytes: int = 0
    ssh: SshInfo | None = None
    is_self: bool = False

    @property
    def os_label(self) -> str:
        return OS_LABELS.get(self.os.lower(), self.os or "—")

    @property
    def primary_ip(self) -> str | None:
        """IPv4 из tailnet (IPv6 оставляем как фолбэк)."""
        for ip in self.ips:
            if ":" not in ip:
                return ip
        return self.ips[0] if self.ips else None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "hostname": self.hostname,
            "os": self.os,
            "os_label": self.os_label,
            "online": self.online,
            "tags": self.tags,
            "exit_node": self.exit_node,
            "ips": self.ips,
            "self": self.is_self,
            "ssh": self.ssh.as_dict() if self.ssh else None,
        }


@dataclass(slots=True)
class Edge:
    src: str
    dst: str
    path: PathType = "unknown"
    relay: str | None = None
    rtt_ms: float | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0

    @property
    def key(self) -> tuple[str, str]:
        return tuple(sorted((self.src, self.dst)))  # type: ignore[return-value]

    def as_dict(self) -> dict:
        return {
            "src": self.src,
            "dst": self.dst,
            "path": self.path,
            "relay": self.relay,
            "rtt_ms": self.rtt_ms,
            "rx_bytes": self.rx_bytes,
            "tx_bytes": self.tx_bytes,
        }


@dataclass(slots=True)
class Snapshot:
    nodes: dict[str, Node]
    edges: list[Edge]
    provider: str = "mock"
    ts: float = field(default_factory=time.time)
    self_id: str | None = None

    @property
    def online(self) -> int:
        return sum(1 for n in self.nodes.values() if n.online)

    @property
    def direct_paths(self) -> int:
        return sum(1 for e in self.edges if e.path == "direct")

    @property
    def relay_paths(self) -> int:
        return sum(1 for e in self.edges if e.path == "relay")

    @property
    def avg_rtt(self) -> float | None:
        values = [e.rtt_ms for e in self.edges if e.rtt_ms is not None]
        return round(sum(values) / len(values), 1) if values else None

    def as_dict(self) -> dict:
        return {
            "ts": self.ts,
            "provider": self.provider,
            "self_id": self.self_id,
            "nodes": [n.as_dict() for n in self.nodes.values()],
            "edges": [e.as_dict() for e in self.edges],
            "summary": {
                "nodes": len(self.nodes),
                "online": self.online,
                "direct": self.direct_paths,
                "relay": self.relay_paths,
                "avg_rtt": self.avg_rtt,
            },
        }
