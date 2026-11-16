from __future__ import annotations

import xml.etree.ElementTree as ET

from meshmap.layout import layout
from meshmap.models import Edge, Node, Snapshot
from meshmap.providers.cli import TailscaleCliProvider
from meshmap.providers.mock import MockProvider
from meshmap.render import render_badge, render_svg


def test_mock_is_deterministic():
    a = MockProvider(seed=7).snapshot(3).as_dict()
    b = MockProvider(seed=7).snapshot(3).as_dict()
    a.pop("ts"), b.pop("ts")
    assert a == b


def test_mock_has_both_path_types():
    snap = MockProvider(seed=7).snapshot(1)
    assert snap.direct_paths > 0
    assert snap.relay_paths > 0
    assert snap.online == len(snap.nodes)


def test_mock_degrades_periodically():
    paths = {MockProvider(seed=7).snapshot(tick).relay_paths for tick in range(1, 20)}
    assert max(paths) > min(paths)


def test_tailscale_json_is_parsed():
    payload = {
        "Self": {
            "ID": "self",
            "HostName": "demo",
            "OS": "windows",
            "Online": True,
            "TailscaleIPs": ["100.64.0.1"],
        },
        "Peers": {
            "p1": {
                "ID": "p1",
                "HostName": "home-server",
                "OS": "linux",
                "Online": True,
                "CurAddr": "192.168.1.5:41641",
                "Relay": "fra",
                "TailscaleIPs": ["100.64.0.2"],
                "RxBytes": 10,
                "TxBytes": 20,
            },
            "p2": {
                "ID": "p2",
                "HostName": "vps-ams",
                "OS": "linux",
                "Online": False,
                "CurAddr": "",
                "Relay": "ams",
                "TailscaleIPs": ["100.64.0.3"],
            },
        },
    }
    snapshot = TailscaleCliProvider(binary="unused").parse(payload)

    assert len(snapshot.nodes) == 3
    assert snapshot.nodes["p2"].online is False
    by_dst = {edge.dst: edge for edge in snapshot.edges}
    assert by_dst["p1"].path == "direct"
    assert by_dst["p2"].path == "relay"
    assert by_dst["p2"].relay == "ams"


def test_tailscale_json_accepts_singular_peer_key():
    payload = {
        "Self": {"ID": "self", "HostName": "demo", "OS": "windows", "Online": True},
        "Peer": {
            "nodekey:abc": {
                "ID": "ns1",
                "HostName": "server",
                "OS": "linux",
                "Online": True,
                "CurAddr": "",
                "Relay": "waw",
                "TailscaleIPs": ["100.64.0.7", "fd7a:115c:a1e0::d36:f01f"],
            }
        },
    }
    snapshot = TailscaleCliProvider(binary="unused").parse(payload)

    assert len(snapshot.nodes) == 2
    assert snapshot.self_id == "self"
    assert snapshot.nodes["self"].is_self is True
    assert snapshot.nodes["ns1"].primary_ip == "100.64.0.7"
    assert snapshot.edges[0].path == "relay"
    assert snapshot.edges[0].relay == "waw"


def test_diff_reports_path_and_latency_changes():
    from meshmap.diff import diff

    nodes = {"a": Node(id="a", hostname="a"), "b": Node(id="b", hostname="b")}
    before = Snapshot(nodes=nodes, edges=[Edge(src="a", dst="b", path="direct", rtt_ms=12)], ts=1)
    after = Snapshot(
        nodes=nodes,
        edges=[Edge(src="a", dst="b", path="relay", relay="fra", rtt_ms=140)],
        ts=2,
    )

    messages = [event["message"] for event in diff(before, after, ts=2)]
    assert any("прямой → DERP fra" in message for message in messages)
    assert any("RTT" in message for message in messages)


def test_diff_reports_offline_node():
    from meshmap.diff import diff

    before = Snapshot(nodes={"a": Node(id="a", hostname="a")}, edges=[], ts=1)
    after = Snapshot(nodes={"a": Node(id="a", hostname="a", online=False)}, edges=[], ts=2)

    events = diff(before, after, ts=2)
    assert events[0]["kind"] == "warn"
    assert "офлайн" in events[0]["message"]


def test_layout_is_stable_and_inside_canvas():
    ids = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    first = layout(ids, edges, width=1200, height=720)
    second = layout(ids, edges, width=1200, height=720)
    assert first == second
    for x, y in first.values():
        assert 0 < x < 1200
        assert 0 < y < 720


def test_layout_without_edges_makes_a_ring():
    positions = layout(["a", "b", "c", "d"], [], width=1200, height=720)
    assert len(positions) == 4


def test_svg_is_valid_and_has_no_ips():
    snapshot = MockProvider(seed=7).snapshot(1)
    positions = layout(list(snapshot.nodes), [e.key for e in snapshot.edges])

    svg = render_svg(snapshot, positions)
    root = ET.fromstring(svg)

    assert root.tag.endswith("svg")
    assert "home-server" in svg
    assert "100." not in svg
    assert "192.168." not in svg


def test_badge_renders_five_metrics():
    snapshot = MockProvider(seed=7).snapshot(1)
    badge = render_badge(snapshot)
    assert badge.count("<text") >= 10
    assert "DERP" in badge


def test_svg_marks_clickable_nodes_and_sftp():
    snapshot = MockProvider(seed=7).snapshot(1)
    positions = layout(list(snapshot.nodes), [e.key for e in snapshot.edges])
    svg = render_svg(snapshot, positions)

    assert 'data-id="server"' in svg
    assert "SFTP" in svg
    assert "EXIT" in svg


def test_sftp_url_uses_tailnet_address():
    from meshmap.filezilla import sftp_url, ssh_command

    node = Node(id="n", hostname="server", ips=["100.64.0.5"])
    assert sftp_url(node, "demo") == "sftp://demo@100.64.0.5:22/"
    assert ssh_command(node, "root", 2222) == "ssh -p 2222 root@100.64.0.5"


def test_sites_xml_is_valid_filezilla_import():
    from meshmap.filezilla import sites_xml

    snapshot = MockProvider(seed=7).snapshot(1)
    root = ET.fromstring(sites_xml(snapshot, lambda hostname: "demo"))
    servers = root.findall(".//Server")

    assert len(servers) == len(snapshot.nodes)
    assert {s.findtext("Name") for s in servers} == {n.hostname for n in snapshot.nodes.values()}
    assert all(s.findtext("Protocol") == "1" for s in servers)
    assert all(s.findtext("Host").startswith("100.") for s in servers)


def test_ssh_probe_reads_banner():
    import asyncio

    from meshmap.sshprobe import probe

    async def scenario():
        async def handler(reader, writer):
            writer.write(b"SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            return await probe("127.0.0.1", port, timeout=2)
        finally:
            server.close()
            await server.wait_closed()

    info = asyncio.run(scenario())
    assert info.state == "open"
    assert info.banner == "OpenSSH_9.6p1"
    assert info.open is True


def test_launch_passes_private_key_only_to_winscp(tmp_path, monkeypatch):
    from meshmap import filezilla

    exe = tmp_path / "WinSCP.exe"
    exe.write_text("stub", encoding="utf-8")
    key = tmp_path / "id_ed25519.ppk"
    key.write_text("stub", encoding="utf-8")
    calls: list[list[str]] = []

    class FakePopen:
        def __init__(self, args, **kwargs):
            calls.append(args)

    monkeypatch.setattr(filezilla.subprocess, "Popen", FakePopen)
    url = "sftp://demo@100.64.0.5:22/"

    assert filezilla.launch("winscp", url, str(exe), str(key))[0] is True
    assert filezilla.launch("filezilla", url, str(exe), str(key))[0] is True

    assert calls[0][1:] == [url, f"-privatekey={key}"]
    assert calls[1][1:] == [url]


def test_settings_reads_ssh_port(monkeypatch):
    from meshmap.config import Settings

    monkeypatch.setenv("MESHMAP_SSH_PORT", "2222")
    monkeypatch.setenv("MESHMAP_SSH_USERS", "server=root, vps-ams=deploy")
    monkeypatch.setenv("MESHMAP_SSH_KEY", r"C:\Users\me\.ssh\id_ed25519.ppk")

    settings = Settings.from_env()
    assert settings.ssh_port == 2222
    assert settings.user_for("server") == "root"
    assert settings.user_for("vps-ams") == "deploy"
    assert settings.ssh_key == r"C:\Users\me\.ssh\id_ed25519.ppk"


def test_api_exposes_node_detail_and_filezilla_export(tmp_path):
    from fastapi.testclient import TestClient

    from meshmap.config import Settings
    from meshmap.web import create_app

    settings = Settings(provider="mock", db_path=str(tmp_path / "test.db"), interval=60)
    with TestClient(create_app(settings)) as client:
        state = client.get("/api/state").json()
        assert state["ready"] is True

        detail = client.get("/api/nodes/server").json()
        assert detail["sftp"]["url"].startswith("sftp://")
        assert detail["ssh"]["open"] is True
        assert detail["links"]

        sites = client.get("/filezilla/sites.xml")
        assert sites.status_code == 200
        assert "<FileZilla3>" in sites.text

        assert client.get("/api/nodes/missing").status_code == 404
