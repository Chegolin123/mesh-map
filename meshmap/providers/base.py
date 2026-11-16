from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Protocol

from ..models import Snapshot


class Provider(Protocol):
    name: str

    async def fetch(self) -> Snapshot: ...


def provider_from_name(name: str, **kwargs: Any) -> Provider:
    from .api import TailscaleApiProvider
    from .cli import TailscaleCliProvider
    from .mock import MockProvider

    match name:
        case "mock":
            return MockProvider(seed=kwargs.get("seed", 7))
        case "tailscale":
            return TailscaleCliProvider(probe_rtt=kwargs.get("probe_rtt", False))
        case "api":
            token = kwargs.get("token") or ""
            if not token:
                raise ValueError("для provider=api нужен TS_API_TOKEN")
            return TailscaleApiProvider(token=token, tailnet=kwargs.get("tailnet", "-"))
        case _:
            raise ValueError(f"неизвестный провайдер: {name}")


class SqliteCache:
    """Небольшой кэш последнего снапшота, чтобы UI поднимался мгновенно."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._payload: dict | None = None
        self._ts = 0.0

    def put(self, snapshot: Snapshot) -> None:
        self._payload = snapshot.as_dict()
        self._ts = time.time()

    def get(self) -> dict | None:
        return self._payload
