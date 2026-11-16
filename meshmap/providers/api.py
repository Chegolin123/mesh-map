from __future__ import annotations

import httpx

from ..models import Edge, Node, Snapshot


class TailscaleApiProvider:
    """Топология через официальный API.

    Ограничение: API не отдаёт тип пути (прямой/DERP), поэтому рёбра помечаются
    как `unknown`, а карта показывает только узлы и их доступность.
    """

    name = "api"

    def __init__(
        self,
        token: str,
        tailnet: str = "-",
        base_url: str = "https://api.tailscale.com",
    ) -> None:
        self.token = token
        self.tailnet = tailnet
        self.base_url = base_url.rstrip("/")

    async def fetch(self) -> Snapshot:
        url = f"{self.base_url}/api/v2/tailnet/{self.tailnet}/devices"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
            resp.raise_for_status()
            devices = resp.json().get("devices", [])
        return self.parse(devices)

    def parse(self, devices: list[dict]) -> Snapshot:
        nodes: dict[str, Node] = {}
        for device in devices:
            ips = list(device.get("addresses") or [])
            node = Node(
                id=str(device.get("id") or device.get("nodeId") or device.get("hostname")),
                hostname=str(device.get("hostname") or device.get("name") or "node"),
                os=str(device.get("os") or "linux"),
                online=bool(device.get("online", False)),
                tags=[t.replace("tag:", "") for t in (device.get("tags") or [])],
                ips=ips,
            )
            nodes[node.id] = node

        edges = [
            Edge(src=a, dst=b, path="unknown")
            for a, b in _chain(list(nodes))
        ]
        return Snapshot(nodes=nodes, edges=edges, provider=self.name)


def _chain(ids: list[str]) -> list[tuple[str, str]]:
    """API не даёт связей — рисуем цепочку, чтобы узлы не висели в пустоте."""
    return [(ids[i], ids[i + 1]) for i in range(len(ids) - 1)]
