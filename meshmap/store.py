from __future__ import annotations

import threading

from .db import History
from .diff import diff
from .layout import layout
from .models import Snapshot
from .render import render_badge, render_svg


class Store:
    """Держит актуальный снапшот, позиции узлов и готовый SVG."""

    def __init__(self, history: History, provider_name: str) -> None:
        self.history = history
        self.provider_name = provider_name
        self.snapshot: Snapshot | None = None
        self.positions: dict[str, tuple[float, float]] = {}
        self.signature: tuple[str, ...] = ()
        self.events: list[dict] = []
        self.svg = ""
        self.error: str | None = None
        self.errors_total = 0
        self.last_ok: float | None = None
        self._lock = threading.Lock()

    def ingest(self, snapshot: Snapshot) -> list[dict]:
        with self._lock:
            events = diff(self.snapshot, snapshot)
            signature = tuple(sorted(snapshot.nodes))
            if signature != self.signature:
                self.positions = layout(
                    list(signature), [e.key for e in snapshot.edges], self.positions
                )
                self.signature = signature
            self.svg = render_svg(snapshot, self.positions, show_title=False)
            self.snapshot = snapshot
            self.error = None
            self.last_ok = snapshot.ts
            self.history.save_snapshot(snapshot)
            self.history.save_events(events)
            self.events = (events + self.events)[:40]
            return events

    def fail(self, message: str) -> None:
        with self._lock:
            self.error = message
            self.errors_total += 1

    def payload(self) -> dict:
        with self._lock:
            if self.snapshot is None:
                return {
                    "ready": False,
                    "provider": self.provider_name,
                    "error": self.error,
                    "svg": "",
                    "nodes": [],
                    "events": [],
                    "summary": {},
                }
            data = self.snapshot.as_dict()
            data["ready"] = True
            data["svg"] = self.svg
            data["badge"] = render_badge(self.snapshot)
            data["events"] = self.events[:30]
            data["error"] = self.error
            return data
