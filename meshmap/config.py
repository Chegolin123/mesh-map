from __future__ import annotations

import getpass
import os
from dataclasses import dataclass, field


def _parse_users(raw: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for chunk in raw.split(","):
        if "=" not in chunk:
            continue
        host, user = chunk.split("=", 1)
        host, user = host.strip(), user.strip()
        if host and user:
            pairs[host] = user
    return pairs


@dataclass(slots=True)
class Settings:
    provider: str = "mock"
    interval: float = 5.0
    db_path: str = "meshmap.db"
    host: str = "127.0.0.1"
    port: int = 8765
    api_token: str = ""
    tailnet: str = "-"
    probe_rtt: bool = False
    probe_ssh: bool = True
    ssh_user: str = field(default_factory=lambda: getpass.getuser() or "root")
    ssh_users: dict[str, str] = field(default_factory=dict)
    ssh_port: int = 22
    ssh_key: str | None = None
    allow_launch: bool = True
    filezilla_path: str | None = None
    probe_timeout: float = 1.5

    def user_for(self, hostname: str) -> str:
        return self.ssh_users.get(hostname) or self.ssh_user

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            provider=os.getenv("MESHMAP_PROVIDER", "mock"),
            interval=float(os.getenv("MESHMAP_INTERVAL", "5")),
            db_path=os.getenv("MESHMAP_DB", "meshmap.db"),
            host=os.getenv("MESHMAP_HOST", "127.0.0.1"),
            port=int(os.getenv("MESHMAP_PORT", "8765")),
            api_token=os.getenv("TS_API_TOKEN", ""),
            tailnet=os.getenv("TS_TAILNET", "-"),
            probe_rtt=_flag("MESHMAP_PROBE_RTT", False),
            probe_ssh=_flag("MESHMAP_PROBE_SSH", True),
            ssh_user=os.getenv("MESHMAP_SSH_USER", getpass.getuser() or "root"),
            ssh_users=_parse_users(os.getenv("MESHMAP_SSH_USERS", "")),
            ssh_port=int(os.getenv("MESHMAP_SSH_PORT", "22")),
            ssh_key=os.getenv("MESHMAP_SSH_KEY") or None,
            allow_launch=_flag("MESHMAP_ALLOW_LAUNCH", True),
            filezilla_path=os.getenv("MESHMAP_FILEZILLA") or None,
            probe_timeout=float(os.getenv("MESHMAP_PROBE_TIMEOUT", "1.5")),
        )


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
