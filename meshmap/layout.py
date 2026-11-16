from __future__ import annotations

import math
import random

Point = tuple[float, float]


def layout(
    node_ids: list[str],
    edges: list[tuple[str, str]],
    prev: dict[str, Point] | None = None,
    width: int = 1200,
    height: int = 720,
    seed: int = 7,
) -> dict[str, Point]:
    """Force-directed раскладка с детерминированным результатом.

    Сохраняем позиции между обновлениями: карта не должна прыгать при каждом
    тике коллектора — меняются только цифры и цвета.
    """
    ids = sorted(set(node_ids))
    n = len(ids)
    if n == 0:
        return {}
    if n == 1:
        return {ids[0]: (width / 2, height / 2)}

    pad_x, pad_y = 130, 95
    prev = prev or {}

    if not edges:
        cx, cy = width / 2, height / 2
        rx, ry = (width - pad_x * 2) / 2, (height - pad_y * 2) / 2
        return {
            nid: (
                cx + rx * math.cos(2 * math.pi * k / n - math.pi / 2),
                cy + ry * math.sin(2 * math.pi * k / n - math.pi / 2),
            )
            for k, nid in enumerate(ids)
        }

    rng = random.Random(seed)
    pos: dict[str, list[float]] = {}
    for nid in ids:
        if nid in prev:
            pos[nid] = [float(prev[nid][0]), float(prev[nid][1])]
        else:
            pos[nid] = [
                rng.uniform(pad_x, width - pad_x),
                rng.uniform(pad_y, height - pad_y),
            ]

    area = (width - 2 * pad_x) * (height - 2 * pad_y)
    k = math.sqrt(area / n)
    pairs = [(a, b) for a, b in edges if a in pos and b in pos]
    temp = min(width, height) / 7

    for _ in range(420):
        disp = {nid: [0.0, 0.0] for nid in ids}
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ids[i], ids[j]
                dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
                d = math.hypot(dx, dy) or 0.01
                force = k * k / d
                ux, uy = dx / d, dy / d
                disp[a][0] += ux * force
                disp[a][1] += uy * force
                disp[b][0] -= ux * force
                disp[b][1] -= uy * force
        for a, b in pairs:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 0.01
            force = d * d / k
            ux, uy = dx / d, dy / d
            disp[a][0] -= ux * force
            disp[a][1] -= uy * force
            disp[b][0] += ux * force
            disp[b][1] += uy * force
        for nid in ids:
            dx, dy = disp[nid]
            # мягкая гравитация к центру: без неё разреженный граф сбивается в угол
            dx += (width / 2 - pos[nid][0]) * 0.045
            dy += (height / 2 - pos[nid][1]) * 0.045
            d = math.hypot(dx, dy) or 0.01
            step = min(d, temp)
            pos[nid][0] = min(max(pos[nid][0] + dx / d * step, pad_x), width - pad_x)
            pos[nid][1] = min(max(pos[nid][1] + dy / d * step, pad_y), height - pad_y)
        temp *= 0.985

    _separate(ids, pos, hx=104, hy=44, width=width, height=height, pad=(pad_x, pad_y))
    return {nid: (pos[nid][0], pos[nid][1]) for nid in ids}


def _separate(
    ids: list[str],
    pos: dict[str, list[float]],
    hx: float,
    hy: float,
    width: int,
    height: int,
    pad: tuple[int, int],
) -> None:
    """Расталкивает прямоугольники узлов, чтобы подписи не наезжали друг на друга."""
    for _ in range(90):
        moved = False
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                ox = hx * 2 - abs(dx)
                oy = hy * 2 - abs(dy)
                if ox <= 0 or oy <= 0:
                    continue
                moved = True
                if ox < oy:
                    shift = ox / 2 * (1 if dx >= 0 else -1)
                    pos[a][0] += shift
                    pos[b][0] -= shift
                else:
                    shift = oy / 2 * (1 if dy >= 0 else -1)
                    pos[a][1] += shift
                    pos[b][1] -= shift
        for nid in ids:
            pos[nid][0] = min(max(pos[nid][0], pad[0]), width - pad[0])
            pos[nid][1] = min(max(pos[nid][1], pad[1]), height - pad[1])
        if not moved:
            break
