from __future__ import annotations

import getpass
import os
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from .models import Node, Snapshot

_WIN_SUBDIR = Path("FileZilla FTP Client") / "filezilla.exe"
_WINSCP_SUBDIR = Path("WinSCP") / "WinSCP.exe"

FILEZILLA_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / _WIN_SUBDIR,
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / _WIN_SUBDIR,
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / _WIN_SUBDIR,
    Path("/usr/bin/filezilla"),
    Path("/Applications/FileZilla.app/Contents/MacOS/filezilla"),
]

WINSCP_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / _WINSCP_SUBDIR,
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / _WINSCP_SUBDIR,
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / _WINSCP_SUBDIR,
]

CLIENTS = {
    "filezilla": ("FileZilla", FILEZILLA_CANDIDATES),
    "winscp": ("WinSCP", WINSCP_CANDIDATES),
}


def find_client(explicit: str | None = None) -> tuple[str, str] | None:
    """Возвращает (kind, путь): сначала FileZilla, потом WinSCP.

    Оба понимают `sftp://user@host:port/`, поэтому диплинк одинаковый.
    """
    if explicit:
        if not Path(explicit).exists():
            return None
        kind = "winscp" if "winscp" in Path(explicit).name.lower() else "filezilla"
        return kind, explicit

    for kind in ("filezilla", "winscp"):
        found = shutil.which(kind)
        if found:
            return kind, found
    for kind, (_, candidates) in CLIENTS.items():
        for candidate in candidates:
            if candidate.exists():
                return kind, str(candidate)
    return None


def find_filezilla(explicit: str | None = None) -> str | None:
    client = find_client(explicit)
    return client[1] if client and client[0] == "filezilla" else None


def sftp_url(node: Node, user: str, port: int = 22, path: str = "/") -> str:
    host = node.primary_ip or node.hostname
    return f"sftp://{user}@{host}:{port}{path}"


def ssh_command(node: Node, user: str, port: int = 22) -> str:
    host = node.primary_ip or node.hostname
    return f"ssh -p {port} {user}@{host}"


def default_key() -> str | None:
    """WinSCP умеет только PuTTY-формат, поэтому ищем .ppk рядом с ключами."""
    home = Path.home() / ".ssh"
    for name in ("id_ed25519.ppk", "id_rsa.ppk", "id_ecdsa.ppk"):
        candidate = home / name
        if candidate.exists():
            return str(candidate)
    return None


def launch(
    kind: str,
    url: str,
    binary: str | None = None,
    key: str | None = None,
) -> tuple[bool, str]:
    """Открывает FileZilla или WinSCP с готовым sftp:// URL.

    Пароль в URL не передаётся: клиент спросит его сам или возьмёт ключ.
    """
    if binary:
        exe: str | None = binary if Path(binary).exists() else None
    else:
        client = find_client()
        exe = client[1] if client and client[0] == kind else None
    if not exe:
        label = CLIENTS.get(kind, (kind,))[0]
        return False, f"{label} не найден"
    args = [exe, url]
    if kind == "winscp" and key and Path(key).exists():
        args.append(f"-privatekey={key}")
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    subprocess.Popen(  # noqa: S603 — запуск локального GUI по явному действию пользователя
        args,
        creationflags=flags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True, exe


def sites_xml(snapshot: Snapshot, user_for) -> str:
    """Файл для Site Manager: File → Import в FileZilla.

    Один импорт — и все онлайн-узлы сети появляются в списке сайтов.
    Пароли не экспортируются: FileZilla спросит при первом подключении.
    """
    nodes = [n for n in snapshot.nodes.values() if n.online and n.ips]
    nodes.sort(key=lambda n: n.hostname)

    items: list[str] = []
    for node in nodes:
        user = user_for(node.hostname)
        port = node.ssh.port if node.ssh else 22
        path = node.primary_ip or node.hostname
        comment = " · ".join(
            part
            for part in [
                "mesh-map",
                node.os_label,
                node.ssh.banner if node.ssh and node.ssh.banner else "",
                "через DERP" if _relayed(snapshot, node.id) else "",
            ]
            if part
        )
        items.append(
            "\n".join(
                [
                    "      <Server>",
                    f"        <Host>{escape(path)}</Host>",
                    f"        <Port>{port}</Port>",
                    "        <Protocol>1</Protocol>",
                    "        <Type>0</Type>",
                    f"        <User>{escape(user)}</User>",
                    "        <Pass/>",
                    "        <Logontype>1</Logontype>",
                    f"        <Name>{escape(node.hostname)}</Name>",
                    f"        <Comments>{escape(comment)}</Comments>",
                    "      </Server>",
                ]
            )
        )

    body = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        "<FileZilla3>\n"
        "  <Servers>\n"
        '    <Folder expanded="1">\n'
        f"{body}\n"
        "    </Folder>\n"
        "  </Servers>\n"
        "</FileZilla3>\n"
    )


def single_site_xml(node: Node, user: str) -> str:
    snapshot = Snapshot(nodes={node.id: node}, edges=[], provider="mesh-map")
    return sites_xml(snapshot, lambda _: user)


def _relayed(snapshot: Snapshot, node_id: str) -> bool:
    return any(node_id in (e.src, e.dst) and e.path == "relay" for e in snapshot.edges)


def default_user() -> str:
    return getpass.getuser() or "root"
