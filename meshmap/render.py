from __future__ import annotations

import html
import math
import time

from .layout import Point
from .models import Snapshot

BG_TOP = "#0b1117"
BG_BOTTOM = "#070a0e"
GRID = "#141d27"
GREEN = "#3ddc97"
AMBER = "#f5a524"
GREY = "#5c6b7a"
TEXT = "#e6edf3"
MUTED = "#8090a0"
BORDER = "#213040"

BOX_W, BOX_H = 168, 54


def render_svg(
    snapshot: Snapshot,
    positions: dict[str, Point],
    width: int = 1200,
    height: int = 720,
    show_title: bool = True,
) -> str:
    out: list[str] = []
    pad_top = 58 if show_title else 0
    total_h = height + pad_top
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_h}" '
        f'width="{width}" height="{total_h}" role="img" aria-label="mesh-map">'
    )
    out.append(_defs(width, height))
    out.append(f'<rect width="{width}" height="{total_h}" fill="url(#bg)"/>')
    out.append(f'<rect width="{width}" height="{total_h}" fill="url(#dots)"/>')

    if show_title:
        out.extend(_title_block(snapshot, width))

    out.append(f'<g transform="translate(0,{pad_top})">')

    traffic_max = max((e.rx_bytes + e.tx_bytes for e in snapshot.edges), default=1)
    for edge in snapshot.edges:
        src = positions.get(edge.src)
        dst = positions.get(edge.dst)
        if not src or not dst:
            continue
        out.append(_edge(edge, src, dst, snapshot, traffic_max))

    for node in sorted(snapshot.nodes.values(), key=lambda n: n.id):
        point = positions.get(node.id)
        if point:
            out.append(_node(node, point))

    out.append(_legend(width, height, snapshot))
    out.append(
        f'<text x="{width - 26}" y="{height - 22}" text-anchor="end" class="foot">'
        f"обновлено {time.strftime('%H:%M:%S', time.localtime(snapshot.ts))}</text>"
    )
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def _defs(width: int, height: int) -> str:
    return f"""<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{BG_TOP}"/><stop offset="1" stop-color="{BG_BOTTOM}"/>
</linearGradient>
<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse">
  <circle cx="1.4" cy="1.4" r="1.1" fill="{GRID}"/>
</pattern>
<filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
  <feGaussianBlur stdDeviation="4" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<style>
  text {{ font-family: "JetBrains Mono", "Cascadia Mono", Consolas, ui-monospace, monospace; }}
  .brand {{ font-size: 23px; font-weight: 700; fill: {TEXT}; letter-spacing: .4px; }}
  .sub {{ font-size: 12.5px; fill: {MUTED}; }}
  .foot {{ font-size: 11px; fill: {MUTED}; }}
  .nh {{ font-size: 13.5px; font-weight: 600; fill: {TEXT}; }}
  .ns {{ font-size: 11px; fill: {MUTED}; }}
  .badge {{ font-size: 9px; fill: #cfd8e3; letter-spacing: .6px; }}
  .nbox {{ fill: #111a23; stroke: {BORDER}; stroke-width: 1; }}
  .node.off .nbox {{ fill: #0e141a; stroke: #2a3542; }}
  .node.off .nh, .node.off .ns {{ fill: #61707e; }}
  .node.on .nbox {{ stroke: #2b4256; }}
  .node {{ cursor: pointer; }}
  .node:hover .nbox {{ stroke: #4d7fa8; }}
  .edge {{ fill: none; stroke-linecap: round; }}
  .edge.direct {{ stroke: {GREEN}; }}
  .edge.relay {{ stroke: {AMBER}; stroke-dasharray: 7 7; animation: dash 1.8s linear infinite; }}
  .edge.unknown {{ stroke: {GREY}; stroke-dasharray: 2 6; }}
  .edge.dead {{ opacity: .3; }}
  .edge-label {{ font-size: 10.5px; fill: {MUTED}; }}
  .elabel-bg {{ fill: {BG_BOTTOM}; opacity: .88; }}
  @keyframes dash {{ to {{ stroke-dashoffset: -28; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .edge.relay {{ animation: none; }}
  }}
</style>
</defs>"""


def _title_block(snapshot: Snapshot, width: int) -> list[str]:
    avg = snapshot.avg_rtt
    parts = [
        f"{len(snapshot.nodes)} узлов",
        f"{snapshot.online} онлайн",
        f"{snapshot.direct_paths} прямых",
        f"{snapshot.relay_paths} DERP",
    ]
    if avg is not None:
        parts.append(f"средний RTT {avg:.0f} мс")
    return [
        '<text x="34" y="34" class="brand">mesh-map</text>',
        f'<text x="34" y="53" class="sub">{html.escape(" · ".join(parts))}</text>',
        f'<text x="{width - 34}" y="34" text-anchor="end" class="sub">'
        f"{html.escape(snapshot.provider)}</text>",
    ]


def _edge(edge, src: Point, dst: Point, snapshot: Snapshot, traffic_max: int) -> str:
    x1, y1 = src
    x2, y2 = dst
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / dist, dx / dist
    bend = 16 if (sum(map(ord, edge.key[0] + edge.key[1])) % 2) else -16
    cx = (x1 + x2) / 2 + nx * bend
    cy = (y1 + y2) / 2 + ny * bend

    weight = max(1.3, min(4.2, 1.3 + math.log10(1 + (edge.rx_bytes + edge.tx_bytes)) * 0.45))
    traffic = max(1, edge.rx_bytes + edge.tx_bytes)
    weight *= 0.75 + 0.5 * (traffic / traffic_max)
    opacity = 0.95 if _online(snapshot, edge) else 0.35
    css_class = f"edge {edge.path}" + ("" if _online(snapshot, edge) else " dead")

    a = _name(snapshot, edge.src)
    b = _name(snapshot, edge.dst)
    path_label = {
        "direct": "прямой",
        "relay": f"DERP {edge.relay or ''}".strip(),
        "unknown": "нет данных",
    }[edge.path]
    rtt = f" · {edge.rtt_ms:.0f} мс" if edge.rtt_ms is not None else ""
    title = f"{a} ↔ {b} · {path_label}{rtt}"

    out = [
        f'<path class="{css_class}" d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" '
        f'stroke-width="{weight:.2f}" opacity="{opacity}">'
        f"<title>{html.escape(title)}</title></path>"
    ]

    if edge.rtt_ms is not None and edge.path != "unknown":
        lx = 0.25 * x1 + 0.5 * cx + 0.25 * x2
        ly = 0.25 * y1 + 0.5 * cy + 0.25 * y2
        label = f"{edge.rtt_ms:.0f} мс"
        w = len(label) * 6.4 + 10
        out.append(
            f'<g><rect x="{lx - w / 2:.1f}" y="{ly - 8:.1f}" width="{w:.1f}" height="16" rx="5" '
            f'class="elabel-bg"/>'
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" class="edge-label">'
            f"{label}</text></g>"
        )
    return "\n".join(out)


def _node(node, point: Point) -> str:
    x, y = point
    state = "on" if node.online else "off"
    led = GREEN if node.online else GREY
    tags = [t for t in node.tags if t != "exit-node"]
    badges: list[tuple[str, str, str, str]] = []
    if node.ssh and node.ssh.open:
        badges.append(("SFTP", "#0d2a20", "#2c6a51", "#7ff0c0"))
    if node.exit_node:
        badges.append(("EXIT", "#191434", "#3b2f7a", "#bdb2ff"))

    sub = " · ".join([node.os_label, *tags])
    sub = _trunc(sub, max(10, 23 - 7 * len(badges)))
    host = _trunc(node.hostname, 18)

    out = [
        f'<g class="node {state}" data-id="{html.escape(node.id)}" '
        f'transform="translate({x:.1f},{y:.1f})">',
        f'<title>{html.escape(node.hostname)} · {html.escape(node.os_label)}'
        f'{"" if node.online else " · офлайн"}'
        f'{"" if not (node.ssh and node.ssh.open) else " · SSH открыт"}'
        "</title>",
        f'<rect x="{-BOX_W / 2}" y="{-BOX_H / 2}" width="{BOX_W}" height="{BOX_H}" '
        f'rx="13" class="nbox"/>',
        f'<circle cx="{-BOX_W / 2 + 16}" cy="{-8}" r="3.6" fill="{led}"'
        + (' filter="url(#glow)"' if node.online else "")
        + "/>",
        f'<text x="{-BOX_W / 2 + 27}" y="-3" class="nh">{html.escape(host)}</text>',
        f'<text x="{-BOX_W / 2 + 16}" y="16" class="ns">{html.escape(sub)}</text>',
    ]

    for index, (label, fill, stroke, color) in enumerate(badges):
        bx = BOX_W / 2 - 10 - 34 - index * 38
        out.append(
            f'<g><rect x="{bx:.1f}" y="4" width="34" height="16" rx="5" fill="{fill}" '
            f'stroke="{stroke}"/>'
            f'<text x="{bx + 17:.1f}" y="15.5" text-anchor="middle" class="badge" '
            f'fill="{color}">{label}</text></g>'
        )
    out.append("</g>")
    return "\n".join(out)


def _legend(width: int, height: int, snapshot: Snapshot) -> str:
    y = height - 26
    items = [
        (GREEN, "прямой"),
        (AMBER, "DERP-реле"),
        (GREY, "нет данных"),
    ]
    out = []
    x = 34
    for color, label in items:
        dash = ' stroke-dasharray="7 7"' if label == "DERP-реле" else ""
        if label == "нет данных":
            dash = ' stroke-dasharray="2 6"'
        out.append(
            f'<line x1="{x}" y1="{y}" x2="{x + 22}" y2="{y}" stroke="{color}" '
            f'stroke-width="2.4"{dash}/>'
        )
        out.append(f'<text x="{x + 30}" y="{y + 4}" class="foot">{label}</text>')
        x += 34 + len(label) * 7
    return "\n".join(out)


def render_badge(snapshot: Snapshot) -> str:
    width, height = 440, 92
    avg = f"{snapshot.avg_rtt:.0f} мс" if snapshot.avg_rtt is not None else "—"
    cells = [
        ("УЗЛЫ", str(len(snapshot.nodes)), TEXT),
        ("ОНЛАЙН", str(snapshot.online), GREEN),
        ("ПРЯМЫЕ", str(snapshot.direct_paths), GREEN),
        ("DERP", str(snapshot.relay_paths), AMBER),
        ("RTT", avg, TEXT),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="mesh-map badge">',
        _defs(width, height),
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="url(#bg)" '
        f'stroke="{BORDER}"/>',
        f'<circle cx="26" cy="26" r="5" fill="{GREEN}" filter="url(#glow)"/>',
        '<text x="40" y="31" class="brand" style="font-size:17px">mesh-map</text>',
        f'<text x="{width - 22}" y="30" text-anchor="end" class="sub">'
        f"{html.escape(snapshot.provider)} · live topology</text>",
    ]
    x = 24
    for label, value, color in cells:
        out.append(f'<text x="{x}" y="60" class="foot">{label}</text>')
        out.append(
            f'<text x="{x}" y="80" style="font-size:18px;font-weight:700;fill:{color}">'
            f"{value}</text>"
        )
        x += 82
    out.append("</svg>")
    return "\n".join(out)


def _online(snapshot: Snapshot, edge) -> bool:
    a = snapshot.nodes.get(edge.src)
    b = snapshot.nodes.get(edge.dst)
    return bool(a and b and a.online and b.online)


def _name(snapshot: Snapshot, node_id: str) -> str:
    node = snapshot.nodes.get(node_id)
    return node.hostname if node else node_id


def _trunc(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
