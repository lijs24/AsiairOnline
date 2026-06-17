"""Route permission / input-validation tests.

These exercise the *real* DashboardHandler gate methods and route dispatch
without binding a socket.  A handler is built with ``__new__`` (so
``BaseHTTPRequestHandler.__init__`` — which would read from a socket — never
runs) and given a fake server, a client address and a stubbed JSON body; its
``_send_json`` / ``_send_bytes`` are captured so we can assert the HTTP status.
No device, network or real server is involved.
"""
from __future__ import annotations

import io
import json
import threading
import types
from http import HTTPStatus

import pytest

from asiairbridge import web
from asiairbridge.web import DashboardHandler


class _StubMaterials:
    def __init__(self) -> None:
        self.scan_called = False
        self.warmer_called = False

    def start_scan(self, force: bool = False) -> dict:
        self.scan_called = True
        return {"ok": True, "running": True}

    def set_warmer_enabled(self, enabled: bool) -> dict:
        self.warmer_called = True
        return {"ok": True, "enabled": enabled}


def make_handler(*, read_only=False, allow_remote_actions=False,
                 client_ip="127.0.0.1", body=None, materials=None):
    handler = DashboardHandler.__new__(DashboardHandler)
    raw = json.dumps(body or {}).encode("utf-8")
    handler.server = types.SimpleNamespace(
        read_only=read_only,
        allow_remote_actions=allow_remote_actions,
        config=types.SimpleNamespace(root="/tmp"),
        materials=materials if materials is not None else _StubMaterials(),
        camera_operations={},
        camera_operations_lock=threading.Lock(),
        camera_cache=types.SimpleNamespace(
            patch_from_action=lambda *a, **k: None,
            trigger=lambda *a, **k: None,
        ),
    )
    handler.client_address = (client_ip, 54321)
    handler.headers = {"Content-Length": str(len(raw))}
    handler.rfile = io.BytesIO(raw)
    handler.responses = []
    handler._send_json = lambda payload, status=HTTPStatus.OK: handler.responses.append(
        ("json", payload, int(status)))
    handler._send_bytes = lambda data, content_type, *a, **k: handler.responses.append(
        ("bytes", content_type, 200))
    return handler


def last_status(handler):
    return handler.responses[-1][2] if handler.responses else None


# ── gate primitives ────────────────────────────────────────────────────────
class TestGatePrimitives:
    def test_actions_blocked_when_read_only(self):
        h = make_handler(read_only=True, allow_remote_actions=True, client_ip="127.0.0.1")
        assert h._actions_allowed() is False
        with pytest.raises(PermissionError):
            h._require_actions_allowed()

    def test_actions_allowed_loopback_without_remote(self):
        h = make_handler(read_only=False, allow_remote_actions=False, client_ip="127.0.0.1")
        assert h._actions_allowed() is True

    def test_actions_blocked_remote_without_allow(self):
        h = make_handler(read_only=False, allow_remote_actions=False, client_ip="100.127.11.80")
        assert h._actions_allowed() is False

    def test_actions_allowed_remote_with_allow(self):
        # The live 8794 instance: --allow-remote-actions, accessed remotely.
        h = make_handler(read_only=False, allow_remote_actions=True, client_ip="100.127.11.80")
        assert h._actions_allowed() is True

    def test_local_write_blocked_when_read_only(self):
        with pytest.raises(PermissionError):
            make_handler(read_only=True)._require_local_write()

    def test_local_write_allowed_when_writable(self):
        make_handler(read_only=False)._require_local_write()  # must not raise


# ── POST route wiring (gate is actually invoked by the dispatch) ────────────
class TestPostGates:
    def test_scan_blocked_when_read_only(self):
        h = make_handler(read_only=True, client_ip="127.0.0.1")
        h.path = "/api/materials/scan"
        h.do_POST()
        assert last_status(h) == HTTPStatus.FORBIDDEN
        assert h.server.materials.scan_called is False

    def test_scan_allowed_when_writable(self):
        h = make_handler(read_only=False, client_ip="127.0.0.1")
        h.path = "/api/materials/scan"
        h.do_POST()
        assert last_status(h) == HTTPStatus.OK
        assert h.server.materials.scan_called is True

    def test_warmer_blocked_when_read_only(self):
        h = make_handler(read_only=True, body={"enabled": True})
        h.path = "/api/materials/warmer"
        h.do_POST()
        assert last_status(h) == HTTPStatus.FORBIDDEN
        assert h.server.materials.warmer_called is False

    def test_camera_action_blocked_when_read_only(self, monkeypatch):
        called = {"v": False}
        monkeypatch.setattr(web, "camera_action_response",
                            lambda *a, **k: called.__setitem__("v", True) or {"ok": True, "operation": {}})
        h = make_handler(read_only=True,
                         body={"device": "d60", "session_id": "s1", "action": "apply_exposure"})
        h.path = "/api/camera-action"
        h.do_POST()
        assert last_status(h) == HTTPStatus.FORBIDDEN
        assert called["v"] is False  # the device write was never reached

    def test_camera_action_blocked_remote_without_allow(self, monkeypatch):
        called = {"v": False}
        monkeypatch.setattr(web, "camera_action_response",
                            lambda *a, **k: called.__setitem__("v", True) or {"ok": True, "operation": {}})
        h = make_handler(read_only=False, allow_remote_actions=False, client_ip="100.127.11.80",
                         body={"device": "d60", "session_id": "s1", "action": "apply_exposure"})
        h.path = "/api/camera-action"
        h.do_POST()
        assert last_status(h) == HTTPStatus.FORBIDDEN
        assert called["v"] is False

    def test_control_role_controller_blocked_remote_without_allow(self, monkeypatch):
        monkeypatch.setattr(web, "update_control_role", lambda *a, **k: {"ok": True})
        h = make_handler(read_only=False, allow_remote_actions=False, client_ip="100.127.11.80",
                         body={"device": "d60", "role": "controller", "session_id": "s1"})
        h.path = "/api/control-role"
        h.do_POST()
        assert last_status(h) == HTTPStatus.FORBIDDEN

    def test_control_role_controller_allowed_with_remote_actions(self, monkeypatch):
        # Must not break the live 8794 usage (take control over Tailscale).
        monkeypatch.setattr(web, "update_control_role", lambda *a, **k: {"ok": True})
        h = make_handler(read_only=False, allow_remote_actions=True, client_ip="100.127.11.80",
                         body={"device": "d60", "role": "controller", "session_id": "s1"})
        h.path = "/api/control-role"
        h.do_POST()
        assert last_status(h) == HTTPStatus.OK

    def test_control_role_monitor_never_gated(self, monkeypatch):
        # Switching to monitor / releasing the lease is cooperative, not a write.
        monkeypatch.setattr(web, "update_control_role", lambda *a, **k: {"ok": True})
        h = make_handler(read_only=False, allow_remote_actions=False, client_ip="100.127.11.80",
                         body={"device": "d60", "role": "monitor", "session_id": "s1"})
        h.path = "/api/control-role"
        h.do_POST()
        assert last_status(h) == HTTPStatus.OK


# ── GET render size validation ──────────────────────────────────────────────
class TestRenderSizeValidation:
    def _get(self, monkeypatch, path, query):
        monkeypatch.setattr(web, "render_cached", lambda *a, **k: b"PNG")
        monkeypatch.setattr(web, "render_sky_cached", lambda *a, **k: b"PNG")
        h = make_handler(client_ip="127.0.0.1")
        h.path = f"{path}?{query}"
        h.do_GET()
        return last_status(h)

    def test_mount_render_size_too_large_returns_400(self, monkeypatch):
        assert self._get(monkeypatch, "/api/mount-render", "size=9999") == HTTPStatus.BAD_REQUEST

    def test_mount_render_size_too_small_returns_400(self, monkeypatch):
        assert self._get(monkeypatch, "/api/mount-render", "size=10") == HTTPStatus.BAD_REQUEST

    def test_mount_render_size_non_integer_returns_400(self, monkeypatch):
        assert self._get(monkeypatch, "/api/mount-render", "size=abc") == HTTPStatus.BAD_REQUEST

    def test_mount_render_valid_size_passes(self, monkeypatch):
        # 760 is what the legacy /mount-classic page actually requests.
        assert self._get(monkeypatch, "/api/mount-render", "size=760") == HTTPStatus.OK

    def test_sky_render_size_too_large_returns_400(self, monkeypatch):
        assert self._get(monkeypatch, "/api/sky-render", "size=4096") == HTTPStatus.BAD_REQUEST
