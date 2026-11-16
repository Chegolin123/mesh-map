from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .models import Snapshot


class History:
    """SQLite: снапшоты (для истории и diff после рестарта) + события."""

    def __init__(self, path: str | Path, keep: int = 5000) -> None:
        self.path = str(path)
        self.keep = keep
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                provider TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                node TEXT,
                message TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            """
        )
        self._conn.commit()

    def save_snapshot(self, snapshot: Snapshot) -> None:
        self._conn.execute(
            "INSERT INTO snapshots(ts, provider, payload) VALUES (?, ?, ?)",
            (snapshot.ts, snapshot.provider, json.dumps(snapshot.as_dict(), ensure_ascii=False)),
        )
        self._conn.execute(
            "DELETE FROM snapshots WHERE id <= (SELECT MAX(id) - ? FROM snapshots)",
            (self.keep,),
        )
        self._conn.commit()

    def last_snapshot(self) -> dict | None:
        row = self._conn.execute(
            "SELECT payload FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_events(self, events: list[dict]) -> None:
        if not events:
            return
        self._conn.executemany(
            "INSERT INTO events(ts, kind, node, message) VALUES (?, ?, ?, ?)",
            [(e["ts"], e["kind"], e.get("node"), e["message"]) for e in events],
        )
        self._conn.execute(
            "DELETE FROM events WHERE id <= (SELECT MAX(id) - ? FROM events)",
            (self.keep,),
        )
        self._conn.commit()

    def events(self, limit: int = 40) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, kind, node, message FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def timeline(self, hours: float = 24) -> list[dict]:
        since = time.time() - hours * 3600
        rows = self._conn.execute(
            """SELECT ts,
                      json_extract(payload, '$.summary.nodes') AS nodes,
                      json_extract(payload, '$.summary.online') AS online,
                      json_extract(payload, '$.summary.direct') AS direct,
                      json_extract(payload, '$.summary.relay') AS relay
               FROM snapshots WHERE ts >= ? ORDER BY id""",
            (since,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
