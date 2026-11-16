from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)

from . import __version__
from .config import Settings
from .db import History
from .filezilla import (
    CLIENTS,
    default_key,
    find_client,
    launch,
    sftp_url,
    single_site_xml,
    sites_xml,
    ssh_command,
)
from .providers import provider_from_name
from .render import render_svg
from .sshprobe import probe_many
from .store import Store
from .templates import PAGE


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    provider = provider_from_name(
        settings.provider,
        token=settings.api_token,
        tailnet=settings.tailnet,
        probe_rtt=settings.probe_rtt,
    )
    history = History(settings.db_path)
    store = Store(history, provider.name)

    async def collect() -> None:
        try:
            snapshot = await provider.fetch()
            await _attach_ssh(snapshot, settings, provider.name)
            store.ingest(snapshot)
        except Exception as exc:  # noqa: BLE001 — источник может быть недоступен
            store.fail(f"{type(exc).__name__}: {exc}")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await collect()

        async def loop() -> None:
            while True:
                await asyncio.sleep(settings.interval)
                await collect()

        task = asyncio.create_task(loop())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            history.close()

    app = FastAPI(title="mesh-map", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.provider = provider

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return PAGE

    @app.get("/api/state")
    async def state() -> JSONResponse:
        return JSONResponse(store.payload())

    @app.get("/api/nodes/{node_id}")
    async def node_detail(node_id: str) -> JSONResponse:
        snapshot = store.snapshot
        node = snapshot.nodes.get(node_id) if snapshot else None
        if snapshot is None or node is None:
            return JSONResponse({"error": "узел не найден"}, status_code=404)

        user = settings.user_for(node.hostname)
        port = node.ssh.port if node.ssh else 22
        host = node.primary_ip or node.hostname
        links = []
        for edge in snapshot.edges:
            if node_id not in (edge.src, edge.dst):
                continue
            peer_id = edge.dst if edge.src == node_id else edge.src
            peer = snapshot.nodes.get(peer_id)
            links.append(
                {
                    "id": peer_id,
                    "hostname": peer.hostname if peer else peer_id,
                    "path": edge.path,
                    "relay": edge.relay,
                    "rtt_ms": edge.rtt_ms,
                    "traffic": edge.rx_bytes + edge.tx_bytes,
                }
            )
        return JSONResponse(
            {
                "node": node.as_dict(),
                "ssh": node.ssh.as_dict() if node.ssh else None,
                "sftp": {
                    "url": sftp_url(node, user, port),
                    "host": host,
                    "port": port,
                    "user": user,
                    "available": bool(node.primary_ip) and bool(node.ssh and node.ssh.open),
                },
                "ssh_command": ssh_command(node, user, port),
                "links": links,
                "demo": provider.name == "mock",
            }
        )

    @app.get("/api/filezilla")
    async def filezilla_status() -> JSONResponse:
        client = find_client(settings.filezilla_path)
        kind = client[0] if client else None
        key = settings.ssh_key or default_key()
        return JSONResponse(
            {
                "installed": client is not None,
                "client": kind,
                "label": CLIENTS[kind][0] if kind else None,
                "path": client[1] if client else None,
                "key": key if kind == "winscp" else None,
                "allow_launch": settings.allow_launch,
                "platform": "windows" if os.name == "nt" else "posix",
            }
        )

    @app.post("/api/nodes/{node_id}/filezilla")
    async def open_in_filezilla(node_id: str, request: Request) -> JSONResponse:
        if not settings.allow_launch:
            return JSONResponse(
                {"ok": False, "error": "запуск запрещён: MESHMAP_ALLOW_LAUNCH=0"}, status_code=403
            )
        if not _same_origin(request):
            return JSONResponse({"ok": False, "error": "cross-origin запрещён"}, status_code=403)

        snapshot = store.snapshot
        node = snapshot.nodes.get(node_id) if snapshot else None
        if snapshot is None or node is None:
            return JSONResponse({"ok": False, "error": "узел не найден"}, status_code=404)
        if not node.primary_ip:
            return JSONResponse(
                {"ok": False, "error": "у узла нет tailnet-адреса"}, status_code=409
            )
        if not node.ssh or not node.ssh.open:
            return JSONResponse(
                {"ok": False, "error": "SSH/SFTP-порт не отвечает"}, status_code=409
            )

        client = find_client(settings.filezilla_path)
        if client is None:
            return JSONResponse(
                {"ok": False, "error": "файловый клиент не найден"}, status_code=409
            )
        kind = client[0]
        key = settings.ssh_key or default_key()
        user = settings.user_for(node.hostname)
        url = sftp_url(node, user, node.ssh.port)
        ok, detail = launch(kind, url, settings.filezilla_path, key)
        if not ok:
            return JSONResponse(
                {
                    "ok": False,
                    "error": detail,
                    "url": url,
                    "command": f'{"winscp" if kind == "winscp" else "filezilla"} "{url}"',
                },
                status_code=409,
            )
        return JSONResponse(
            {"ok": True, "url": url, "binary": detail, "client": kind, "key": key}
        )

    @app.get("/api/nodes/{node_id}/site.xml")
    async def node_site(node_id: str) -> Response:
        snapshot = store.snapshot
        node = snapshot.nodes.get(node_id) if snapshot else None
        if snapshot is None or node is None:
            empty = "<FileZilla3><Servers/></FileZilla3>"
            return Response(content=empty, media_type="application/xml")
        xml = single_site_xml(node, settings.user_for(node.hostname))
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{node.hostname}.xml"'},
        )

    @app.get("/filezilla/sites.xml")
    async def filezilla_sites() -> Response:
        snapshot = store.snapshot
        if snapshot is None:
            empty = "<FileZilla3><Servers/></FileZilla3>"
            return Response(content=empty, media_type="application/xml")
        xml = sites_xml(snapshot, settings.user_for)
        return Response(
            content=xml,
            media_type="application/xml; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="mesh-map-sites.xml"'},
        )

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        async def gen():
            last: str | None = None
            idle = 0
            while True:
                payload = json.dumps(store.payload(), ensure_ascii=False, default=str)
                if payload != last:
                    last = payload
                    idle = 0
                    yield f"data: {payload}\n\n"
                else:
                    idle += 1
                    if idle >= 15:
                        idle = 0
                        yield ": keep-alive\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/history")
    async def api_history(limit: int = 40) -> JSONResponse:
        return JSONResponse(
            {
                "events": history.events(limit),
                "timeline": history.timeline(hours=6),
            }
        )

    @app.post("/api/refresh")
    async def refresh() -> JSONResponse:
        await collect()
        return JSONResponse({"ok": store.error is None, "error": store.error})

    @app.get("/graph.svg")
    async def graph_svg(title: int = 0) -> Response:
        data = store.payload()
        svg = data.get("svg", "")
        if title and store.snapshot is not None:
            svg = render_svg(store.snapshot, store.positions, show_title=True)
        return Response(
            content=svg,
            media_type="image/svg+xml; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/badge.svg")
    async def badge_svg() -> Response:
        data = store.payload()
        return Response(
            content=data.get("badge", ""),
            media_type="image/svg+xml; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/metrics")
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(_metrics(store, history), media_type="text/plain; version=0.0.4")

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        snapshot = store.snapshot
        healthy = snapshot is not None and store.error is None
        return JSONResponse(
            {"ok": healthy, "error": store.error, "nodes": len(snapshot.nodes) if snapshot else 0},
            status_code=200 if healthy else 503,
        )

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        return Response(status_code=204)

    return app


def _metrics(store: Store, history: History) -> str:
    snapshot = store.snapshot
    lines = [
        "# HELP meshmap_nodes_total Узлы в сети по состоянию",
        "# TYPE meshmap_nodes_total gauge",
    ]
    if snapshot is None:
        lines.append('meshmap_nodes_total{state="online"} 0')
        lines.append('meshmap_nodes_total{state="offline"} 0')
    else:
        lines.append(f'meshmap_nodes_total{{state="online"}} {snapshot.online}')
        offline = len(snapshot.nodes) - snapshot.online
        lines.append(f'meshmap_nodes_total{{state="offline"}} {offline}')
        lines += [
            "# HELP meshmap_edges_total Связи по типу пути",
            "# TYPE meshmap_edges_total gauge",
            f'meshmap_edges_total{{path="direct"}} {snapshot.direct_paths}',
            f'meshmap_edges_total{{path="relay"}} {snapshot.relay_paths}',
            f'meshmap_edges_total{{path="unknown"}}'
            f" {len(snapshot.edges) - snapshot.direct_paths - snapshot.relay_paths}",
            "# HELP meshmap_edge_rtt_ms Задержка до пира, мс",
            "# TYPE meshmap_edge_rtt_ms gauge",
        ]
        for edge in snapshot.edges:
            if edge.rtt_ms is None:
                continue
            src = snapshot.nodes[edge.src].hostname if edge.src in snapshot.nodes else edge.src
            dst = snapshot.nodes[edge.dst].hostname if edge.dst in snapshot.nodes else edge.dst
            lines.append(
                f'meshmap_edge_rtt_ms{{src="{src}",dst="{dst}",path="{edge.path}"}} {edge.rtt_ms}'
            )
        lines += [
            "# HELP meshmap_ssh_up SSH/SFTP-порт узла отвечает",
            "# TYPE meshmap_ssh_up gauge",
        ]
        for node in snapshot.nodes.values():
            up = 1 if node.ssh and node.ssh.open else 0
            lines.append(f'meshmap_ssh_up{{node="{node.hostname}"}} {up}')
    lines += [
        "# HELP meshmap_last_collect_timestamp_seconds Время последнего успешного сбора",
        "# TYPE meshmap_last_collect_timestamp_seconds gauge",
        f"meshmap_last_collect_timestamp_seconds {store.last_ok or 0:.0f}",
        "# HELP meshmap_collect_errors_total Ошибки сбора",
        "# TYPE meshmap_collect_errors_total counter",
        f"meshmap_collect_errors_total {store.errors_total}",
        "# HELP meshmap_up Сервис отвечает",
        "# TYPE meshmap_up gauge",
        f"meshmap_up {0 if store.error else 1}",
        "# HELP meshmap_history_events_total Событий в истории",
        "# TYPE meshmap_history_events_total gauge",
        f"meshmap_history_events_total {len(history.events(1000))}",
        f"# generated {time.strftime('%Y-%m-%dT%H:%M:%S')}",
    ]
    return "\n".join(lines) + "\n"


async def _attach_ssh(snapshot, settings: Settings, provider_name: str) -> None:
    """Проверяет SSH-порт у онлайн-узлов. Мок уже содержит готовые данные."""
    if provider_name == "mock" or not settings.probe_ssh:
        return
    targets = [
        (node.id, node.primary_ip, settings.ssh_port)
        for node in snapshot.nodes.values()
        if node.online and node.primary_ip
    ]
    if not targets:
        return
    try:
        results = await probe_many(targets, timeout=settings.probe_timeout)
    except Exception:  # noqa: BLE001 — проба не должна ломать сбор топологии
        return
    for node_id, info in results.items():
        node = snapshot.nodes.get(node_id)
        if node is not None:
            node.ssh = info


def _same_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    return origin.rstrip("/") == str(request.base_url).rstrip("/")
