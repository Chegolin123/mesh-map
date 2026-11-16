from __future__ import annotations

import asyncio
import time

from .models import SshInfo


async def probe(host: str, port: int = 22, timeout: float = 1.5) -> SshInfo:
    """Проверяет, слушает ли SSH, и читает баннер версии.

    Никакой аутентификации: TCP-коннект + чтение первой строки протокола,
    поэтому в логах целевой машины не появляется неудачных логинов.
    """
    started = time.perf_counter()
    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        banner = await asyncio.wait_for(reader.readline(), timeout=timeout)
        rtt = round((time.perf_counter() - started) * 1000, 1)
        text = banner.decode("utf-8", errors="replace").strip()
        if text.startswith("SSH-"):
            return SshInfo(port=port, state="open", banner=_short_banner(text), rtt_ms=rtt)
        return SshInfo(port=port, state="closed", banner=None, rtt_ms=rtt)
    except TimeoutError:
        return SshInfo(port=port, state="timeout")
    except OSError:
        return SshInfo(port=port, state="closed")
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


def _short_banner(text: str) -> str:
    # SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13  →  OpenSSH_9.6p1
    parts = text.split("-", 2)
    software = parts[2] if len(parts) == 3 else text
    return software.split(" ")[0][:40]


async def probe_many(
    targets: list[tuple[str, str, int]],
    timeout: float = 1.5,
    concurrency: int = 8,
) -> dict[str, SshInfo]:
    """targets: [(node_id, host, port)] → {node_id: SshInfo}."""
    semaphore = asyncio.Semaphore(concurrency)

    async def one(node_id: str, host: str, port: int) -> tuple[str, SshInfo]:
        async with semaphore:
            return node_id, await probe(host, port, timeout)

    results = await asyncio.gather(*(one(*t) for t in targets))
    return dict(results)
