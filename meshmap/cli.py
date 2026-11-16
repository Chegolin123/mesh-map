from __future__ import annotations

import argparse
import asyncio
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import __version__
from .config import Settings
from .layout import layout
from .providers import provider_from_name
from .render import render_svg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mesh-map",
        description="Живая карта mesh-сети: узлы, прямые пути и DERP-реле.",
    )
    parser.add_argument("--version", action="version", version=f"mesh-map {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="поднять дашборд")
    serve.add_argument("--provider", choices=["mock", "tailscale", "api"], default=None)
    serve.add_argument("--interval", type=float, default=None)
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--db", default=None)
    serve.add_argument("--probe-rtt", action="store_true", help="пинговать пиры (только tailscale)")
    serve.add_argument("--no-browser", action="store_true")

    snap = sub.add_parser("snapshot", help="отрендерить SVG в файл и выйти")
    snap.add_argument("--provider", choices=["mock", "tailscale", "api"], default="mock")
    snap.add_argument("--out", default="mesh.svg")
    snap.add_argument("--width", type=int, default=1200)
    snap.add_argument("--height", type=int, default=720)
    snap.add_argument("--tick", type=int, default=10, help="тик mock-симуляции (для демо)")

    hist = sub.add_parser("history", help="показать последние события")
    hist.add_argument("--db", default="meshmap.db")
    hist.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)

    if args.command == "serve":
        return _serve(args)
    if args.command == "snapshot":
        return _snapshot(args)
    if args.command == "history":
        return _history(args)
    return 1


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .web import create_app

    settings = Settings.from_env()
    if args.provider:
        settings.provider = args.provider
    if args.interval:
        settings.interval = args.interval
    if args.host:
        settings.host = args.host
    if args.port:
        settings.port = args.port
    if args.db:
        settings.db_path = args.db
    settings.probe_rtt = settings.probe_rtt or args.probe_rtt

    url = f"http://{settings.host}:{settings.port}/"
    print(f"mesh-map · provider={settings.provider} · {url}", flush=True)
    if not args.no_browser:
        threading.Thread(
            target=lambda: (time.sleep(1.2), webbrowser.open(url)),
            daemon=True,
        ).start()

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="warning")
    return 0


def _snapshot(args: argparse.Namespace) -> int:
    if args.provider == "mock":
        from .providers.mock import MockProvider

        snapshot = MockProvider(seed=7).snapshot(max(1, args.tick))
    else:
        provider = provider_from_name(args.provider)
        snapshot = asyncio.run(provider.fetch())
    positions = layout(
        list(snapshot.nodes), [e.key for e in snapshot.edges], width=args.width, height=args.height
    )
    svg = render_svg(snapshot, positions, width=args.width, height=args.height, show_title=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(
        f"{out} · {len(snapshot.nodes)} узлов · {snapshot.direct_paths} прямых · "
        f"{snapshot.relay_paths} DERP",
        flush=True,
    )
    return 0


def _history(args: argparse.Namespace) -> int:
    from .db import History

    history = History(args.db)
    events = history.events(args.limit)
    if not events:
        print("событий нет", flush=True)
        return 0
    for event in events:
        stamp = time.strftime("%H:%M:%S", time.localtime(event["ts"]))
        print(f"{stamp}  {event['kind']:<8} {event['message']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
