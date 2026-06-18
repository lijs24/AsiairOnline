from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .camera_cache import CameraStateCache
from .guide_monitor import GuideMonitor
from .plan_ops import PlanMonitor, plan_action_response
from .camera_ops import camera_action_response, camera_status_response, capture_progress_response
from .mount_ops import mount_status_response
from .mount_render import render_cached
from .sky_render import render_sky_cached
from .config import AppConfig, load_config
from .image_preview import cached_image_path, cached_raw_path, current_image_response
from .materials import MaterialLibrary
from .monitor import dashboard_snapshot, read_log_tail, read_lock, scan_source_totals
from .rpc_monitor import init_rpc_monitor_state, rpc_monitor_response
from .web_control import ControlLeaseBusyError, control_state, update_control_role

DASHBOARD_SOURCE_LABEL = "EMMC Images"


class _StreamWriter:
    """Write-only wrapper (no tell/seek) so zipfile streams to the socket via
    data descriptors — no buffering, no temp file, any size."""

    def __init__(self, wfile: Any) -> None:
        self._w = wfile

    def write(self, data: bytes) -> int:
        self._w.write(data)
        return len(data)

    def flush(self) -> None:
        try:
            self._w.flush()
        except OSError:
            pass


def _safe_attachment_name(name: str, default: str = "download") -> str:
    """Sanitise a Content-Disposition filename to a safe ASCII token (keeps
    spaces and common punctuation; non-ASCII/quotes/control chars → '_')."""
    cleaned = "".join(
        c if (ord(c) < 128 and (c.isalnum() or c in " ._-()")) else "_"
        for c in str(name)
    ).strip()
    return cleaned or default


def run_server(
    config_path: str,
    host: str = "127.0.0.1",
    port: int = 8787,
    allow_remote_actions: bool = False,
    read_only: bool = False,
) -> None:
    config = load_config(config_path)
    server = AsiairBridgeServer(
        (host, port),
        DashboardHandler,
        config,
        allow_remote_actions=allow_remote_actions,
        read_only=read_only,
    )
    print(f"asiairbridge web listening on http://{host}:{port}")
    server.serve_forever()


class AsiairBridgeServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address,  # type: ignore[no-untyped-def]
        handler_class,
        config: AppConfig,
        allow_remote_actions: bool = False,
        read_only: bool = False,
    ):
        super().__init__(server_address, handler_class)
        self.config = config
        self.allow_remote_actions = allow_remote_actions
        self.read_only = read_only
        self.camera_operations: dict[str, dict[str, Any]] = {}
        self.camera_operations_lock = threading.Lock()
        self.camera_cache = CameraStateCache(config)
        self.camera_cache.start()
        self.guide_monitor = GuideMonitor(config)
        self.guide_monitor.start()
        self.plan_monitor = PlanMonitor(config)
        self.plan_monitor.start()
        self.materials = MaterialLibrary(config)
        self.materials.start_warmer()
        init_rpc_monitor_state(self)

    def server_close(self) -> None:
        self.camera_cache.stop()
        self.guide_monitor.stop()
        self.plan_monitor.stop()
        self.materials.stop_warmer()
        super().server_close()


def devices_payload(config: AppConfig) -> dict[str, Any]:
    default_device = config.default_device()
    devices = []
    for device in config.enabled_devices():
        devices.append(
            {
                "name": device.name,
                "ip": device.ip,
                "enabled": device.enabled,
                "is_default": device.name == default_device.name,
                "source_roots": [
                    {
                        "label": source.label,
                        "enabled": source.enabled,
                    }
                    for source in config.source_roots_for(device)
                ],
            }
        )
    return {
        "ok": True,
        "default_device": default_device.name,
        "devices": devices,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server: AsiairBridgeServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path in {"/", "/monitor-minterm"}:
                self._send_file(
                    self.server.config.root / "docs" / "ops-overview.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path in {"/preview", "/camera"}:
                self._send_file(
                    self.server.config.root / "docs" / "ops-camera.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path in {"/materials", "/library"}:
                self._send_file(
                    self.server.config.root / "docs" / "ops-materials.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path in {"/materials-admin", "/library-admin"}:
                self._send_file(
                    self.server.config.root / "docs" / "ops-materials-admin.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/mount":
                self._send_file(
                    self.server.config.root / "docs" / "ops-mount.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/advanced":
                self._send_file(
                    self.server.config.root / "docs" / "ops-advanced.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/network":
                self._send_file(
                    self.server.config.root / "docs" / "ops-network.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/guide":
                self._send_file(
                    self.server.config.root / "docs" / "ops-guide.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/plan":
                self._send_file(
                    self.server.config.root / "docs" / "ops-plan.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/plan-design":
                self._send_file(
                    self.server.config.root / "docs" / "ops-plan-design.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/mount-classic":
                # 旧版 GPU 3D 渲染赤道仪页,新前端未包含 3D 能力,保留入口
                self._send_file(
                    self.server.config.root / "docs" / "asiair-mount.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/camera-monitor":
                self._send_file(
                    self.server.config.root / "docs" / "ops-camera-monitor.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/camera-recordings":
                self._send_file(
                    self.server.config.root / "docs" / "ops-camera-recordings.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/api/camera/recordings":
                from .camera_rec import list_recordings_payload
                q = parse_qs(parsed.query)
                self._send_json(list_recordings_payload(
                    q.get("stream", [None])[0], q.get("date", [None])[0]))
            elif parsed.path == "/api/camera/recording-file":
                from .camera_rec import resolve_recording
                q = parse_qs(parsed.query)
                rec_path = resolve_recording(q.get("stream", [None])[0], q.get("name", [None])[0])
                if rec_path is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_download_file(rec_path)
            elif parsed.path == "/api/camera/stats":
                from .camera_rec import stream_stats
                self._send_json(stream_stats())
            elif parsed.path == "/ops-theme.js":
                self._send_file(
                    self.server.config.root / "docs" / "ops-theme.js",
                    "application/javascript; charset=utf-8",
                )
            elif parsed.path.startswith("/fonts/"):
                name = parsed.path[len("/fonts/"):]
                if name.endswith(".woff2") and "/" not in name and ".." not in name:
                    self._send_file(
                        self.server.config.root / "docs" / "fonts" / name,
                        "font/woff2",
                        cache_seconds=86400,
                    )
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            elif parsed.path == "/topbar.js":
                self._send_file(
                    self.server.config.root / "docs" / "asiair-topbar.js",
                    "application/javascript; charset=utf-8",
                )
            elif parsed.path == "/static/asiair-monitor-static-preview.html":
                self._send_file(
                    self.server.config.root / "docs" / "asiair-monitor-static-preview.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/static/asiair-monitor-minterm-live.html":
                self._send_file(
                    self.server.config.root / "docs" / "asiair-monitor-minterm-live.html",
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/drop/asiair-monitor-static-preview.html":
                self._send_file(
                    self.server.config.root / "docs" / "asiair-monitor-static-preview.html",
                    "text/html; charset=utf-8",
                    download_name="asiair-monitor-static-preview.html",
                )
            elif parsed.path == "/drop/asiair-monitor-minterm-live.html":
                self._send_file(
                    self.server.config.root / "docs" / "asiair-monitor-minterm-live.html",
                    "text/html; charset=utf-8",
                    download_name="asiair-monitor-minterm-live.html",
                )
            elif parsed.path == "/api/status":
                payload = dashboard_snapshot(self.server.config, source_label=DASHBOARD_SOURCE_LABEL)
                payload["dashboard_source_label"] = DASHBOARD_SOURCE_LABEL
                payload["web"] = {
                    "client": self.client_address[0],
                    "actions_allowed": self._actions_allowed(),
                    "scan_allowed": self._scan_allowed(),
                    "allow_remote_actions": self.server.allow_remote_actions,
                    "read_only": self.server.read_only,
                }
                self._send_json(payload)
            elif parsed.path == "/api/devices":
                self._send_json(devices_payload(self.server.config))
            elif parsed.path == "/api/ping":
                # 极轻量端点:前端计往返耗时,度量"后端→前端"本会话链路延迟
                self._send_json({"ok": True, "t": datetime.now().isoformat(timespec="milliseconds")})
            elif parsed.path == "/api/log":
                query = parse_qs(parsed.query)
                path = query.get("path", [""])[0]
                self._send_json(read_log_tail(self.server.config, path))
            elif parsed.path == "/api/rpc-monitor":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                category = query.get("category", [None])[0]
                force = query.get("force", ["0"])[0] in {"1", "true", "yes"}
                self._send_json(
                    rpc_monitor_response(
                        self.server,
                        device_name=device,
                        force=force,
                        focus_category=category,
                    )
                )
            elif parsed.path == "/api/capture-progress":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                self._send_json(capture_progress_response(self.server.config, device))
            elif parsed.path == "/api/mount-state":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                self._send_json(mount_status_response(self.server.config, device))
            elif parsed.path == "/api/mount-render":
                query = parse_qs(parsed.query)
                params = {k: query.get(k, [None])[0] for k in (
                    "ra", "dec", "lst", "lat", "pier", "size", "az", "el", "ha",
                    "sky", "eqgrid", "altgrid", "tra", "tdec", "fov", "ground")}
                _size = params.get("size")
                if _size is not None:
                    try:
                        _size_int = int(_size)
                    except (ValueError, TypeError):
                        self._send_json({"ok": False, "error": "size must be an integer"}, HTTPStatus.BAD_REQUEST)
                        return
                    if not (64 <= _size_int <= 2048):
                        self._send_json({"ok": False, "error": "size must be between 64 and 2048"}, HTTPStatus.BAD_REQUEST)
                        return
                self._send_bytes(render_cached(params, str(self.server.config.root)), "image/png")
            elif parsed.path == "/api/sky-render":
                query = parse_qs(parsed.query)
                params = {k: query.get(k, [None])[0] for k in ("ra", "dec", "lst", "lat", "tra", "tdec", "size")}
                _size = params.get("size")
                if _size is not None:
                    try:
                        _size_int = int(_size)
                    except (ValueError, TypeError):
                        self._send_json({"ok": False, "error": "size must be an integer"}, HTTPStatus.BAD_REQUEST)
                        return
                    if not (64 <= _size_int <= 2048):
                        self._send_json({"ok": False, "error": "size must be between 64 and 2048"}, HTTPStatus.BAD_REQUEST)
                        return
                self._send_bytes(render_sky_cached(params), "image/png")
            elif parsed.path == "/api/current-image":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                force = query.get("refresh", ["0"])[0] in {"1", "true", "yes"}
                self._send_json(current_image_response(self.server.config, device, force=force))
            elif parsed.path == "/api/current-image-file":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                self._send_file(cached_image_path(self.server.config, device), "image/png")
            elif parsed.path == "/api/current-image-raw":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                self._send_file(
                    cached_raw_path(self.server.config, device),
                    "application/octet-stream",
                    allow_gzip=True,
                )
            elif parsed.path == "/api/materials/summary":
                self._send_json(self.server.materials.summary())
            elif parsed.path == "/api/materials/admin":
                self._send_json(self.server.materials.admin_overview())
            elif parsed.path == "/api/materials/activity":
                lock = read_lock(self.server.config.project.lock_file)
                downloading = bool(lock.get("active")) and lock.get("pid_alive") is not False
                payload = self.server.materials.activity()
                payload["ok"] = True
                payload["downloading"] = downloading
                payload["download_devices"] = list(lock.get("devices") or []) if downloading else []
                self._send_json(payload)
            elif parsed.path == "/api/materials/browse":
                query = parse_qs(parsed.query)
                self._send_json(
                    self.server.materials.browse(
                        device=query.get("device", [""])[0],
                        source_label=query.get("source", [""])[0],
                        relative_path=query.get("path", [""])[0],
                        q=query.get("q", [None])[0],
                        page=int(query.get("page", ["1"])[0] or 1),
                        page_size=int(query.get("page_size", ["80"])[0] or 80),
                    )
                )
            elif parsed.path == "/api/materials":
                query = parse_qs(parsed.query)
                self._send_json(
                    self.server.materials.list_materials(
                        device=query.get("device", [None])[0],
                        source_label=query.get("source", [None])[0],
                        mode=query.get("mode", [None])[0],
                        frame_type=query.get("frame_type", [None])[0],
                        target=query.get("target", [None])[0],
                        q=query.get("q", [None])[0],
                        page=int(query.get("page", ["1"])[0] or 1),
                        page_size=int(query.get("page_size", ["12"])[0] or 12),
                    )
                )
            elif parsed.path == "/api/materials/preview":
                query = parse_qs(parsed.query)
                item_id = query.get("id", [""])[0]
                force = query.get("force", ["0"])[0] in {"1", "true", "yes"}
                preview = self.server.materials.ensure_preview(item_id, force=force)
                self._send_file(Path(preview["path"]), str(preview["content_type"]))
            elif parsed.path == "/api/materials/thumb":
                query = parse_qs(parsed.query)
                item_id = query.get("id", [""])[0]
                path = self.server.materials.thumbnail_path(item_id)
                if path is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
                    self._send_file(path, content_type)
            elif parsed.path == "/api/materials/file":
                # 单文件原始素材直接下载(带 Content-Length,有进度条)
                query = parse_qs(parsed.query)
                path = self.server.materials.source_file_for(query.get("id", [""])[0])
                if path is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_download_file(path)
            elif parsed.path == "/api/materials/zip":
                # 多选(?ids=逗号分隔)或文件夹(?device=&source=&path=)打包流式下载
                query = parse_qs(parsed.query)
                ids_raw = (query.get("ids", [""])[0] or "").strip()
                if ids_raw:
                    ids = [s for s in ids_raw.split(",") if s]
                    files = self.server.materials.resolve_download(ids=ids)
                    zipname = f"asiair-{len(files)}-files.zip"
                else:
                    device = (query.get("device", [""])[0] or "").strip()
                    source = (query.get("source", [""])[0] or "").strip()
                    folder = (query.get("path", [""])[0] or "").strip()
                    files = self.server.materials.resolve_download(
                        device=device, source=source, folder=folder)
                    leaf = folder.rstrip("/").split("/")[-1] or source or device or "materials"
                    zipname = _safe_attachment_name(f"{device}-{leaf}", "materials") + ".zip"
                self._send_materials_zip(files, zipname)
            elif parsed.path == "/api/materials/preview-status":
                query = parse_qs(parsed.query)
                item_id = query.get("id", [""])[0]
                self._send_json(self.server.materials.preview_status(item_id))
            elif parsed.path == "/api/control-role":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                session_id = query.get("session_id", [""])[0]
                if not device:
                    raise ValueError("device is required")
                self._send_json(control_state(self.server.config, device, session_id=session_id))
            elif parsed.path == "/api/camera-state":
                query = parse_qs(parsed.query)
                device = query.get("device", [None])[0]
                session_id = query.get("session_id", [""])[0]
                live = query.get("live", ["0"])[0] in {"1", "true", "yes"}
                if live:
                    payload = camera_status_response(
                        self.server.config,
                        device_name=device,
                        session_id=session_id,
                        rpc_timeout_seconds=2.5,
                        queue_timeout_seconds=4.0,
                        status_budget_seconds=10.0,
                        priority="foreground",
                    )
                    self.server.camera_cache.store(payload)
                    payload["cache"] = {
                        "from_cache": False,
                        "updated_at": payload.get("snapshot_at"),
                        "age_seconds": 0,
                        "status": "live",
                    }
                    self._send_json(payload)
                else:
                    self._send_json(self.server.camera_cache.get(device, session_id=session_id))
            elif parsed.path == "/api/camera-states":
                query = parse_qs(parsed.query)
                session_id = query.get("session_id", [""])[0]
                self._send_json(self.server.camera_cache.get_all(session_id=session_id))
            elif parsed.path == "/api/guide-states":
                query = parse_qs(parsed.query)
                device = query.get("device", [""])[0]
                gm = self.server.guide_monitor
                self._send_json(gm.get_one(device) if device else gm.get_all())
            elif parsed.path == "/api/plan-state":
                query = parse_qs(parsed.query)
                self._send_json(self.server.plan_monitor.get(query.get("device", [""])[0]))
            elif parsed.path == "/api/guide-log/index":
                query = parse_qs(parsed.query)
                self._send_json(self.server.guide_monitor.list_nights(query.get("device", [""])[0]))
            elif parsed.path == "/api/guide-log":
                query = parse_qs(parsed.query)
                self._send_json(self.server.guide_monitor.read_night(
                    query.get("device", [""])[0], query.get("date", [""])[0]))
            elif parsed.path == "/api/guide-log/raw":
                query = parse_qs(parsed.query)
                device = query.get("device", [""])[0]
                date = query.get("date", [""])[0]
                path = self.server.guide_monitor.night_file(device, date)
                if path is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._send_file(
                        path,
                        "application/x-ndjson; charset=utf-8",
                        download_name=f"guide-{device}-{date}.jsonl",
                    )
            elif parsed.path == "/api/camera-operation":
                query = parse_qs(parsed.query)
                device = query.get("device", [""])[0]
                session_id = query.get("session_id", [""])[0]
                operation_id = query.get("operation_id", [""])[0]
                self._send_json(self._camera_operation_state(device, session_id, operation_id))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json_body()
            if parsed.path == "/api/start":
                self._require_actions_allowed()
                payload["source_label"] = DASHBOARD_SOURCE_LABEL
                self._send_json(start_backup(self.server.config, payload))
            elif parsed.path == "/api/scan-source":
                self._require_scan_allowed()
                device = payload.get("device")
                self._send_json(
                    scan_source_totals(
                        self.server.config,
                        [device] if device else None,
                        [DASHBOARD_SOURCE_LABEL],
                    )
                )
            elif parsed.path == "/api/materials/scan":
                self._require_local_write()
                self._send_json(self.server.materials.start_scan(force=bool(payload.get("force"))))
            elif parsed.path == "/api/materials/warmer":
                self._require_local_write()
                self._send_json(self.server.materials.set_warmer_enabled(bool(payload.get("enabled"))))
            elif parsed.path == "/api/control-role":
                device = str(payload.get("device") or "").strip()
                session_id = str(payload.get("session_id") or "").strip()
                role = str(payload.get("role") or "").strip().lower()
                session_label = str(payload.get("session_label") or "").strip() or None
                if role == "controller":
                    # Claiming control is a write action; switching to monitor /
                    # releasing the lease is cooperative state and never gated.
                    self._require_actions_allowed()
                if not device:
                    raise ValueError("device is required")
                self._send_json(
                    update_control_role(
                        self.server.config,
                        device_name=device,
                        session_id=session_id,
                        client_ip=self.client_address[0],
                        role=role,
                        session_label=session_label,
                    )
                )
            elif parsed.path == "/api/camera-action":
                device = str(payload.get("device") or "").strip()
                session_id = str(payload.get("session_id") or "").strip()
                action = str(payload.get("action") or "").strip()
                if not device:
                    raise ValueError("device is required")
                if not session_id:
                    raise ValueError("session_id is required")
                operation_id = str(payload.get("operation_id") or "").strip() or (
                    f"{session_id}:{action}:{time.time():.3f}"
                )
                self._update_camera_operation(
                    device,
                    session_id,
                    operation_id,
                    {
                        "step": 0,
                        "total": 1,
                        "label": "准备相机操作",
                        "state": "running",
                        "detail": action,
                    },
                )
                try:
                    self._require_actions_allowed()  # P0-1: actions gate before controller check
                    self._require_controller_for_device(device, session_id)
                    result = camera_action_response(
                        self.server.config,
                        device_name=device,
                        action=action,
                        payload=payload,
                        session_id=session_id,
                        progress_callback=lambda update: self._update_camera_operation(
                            device,
                            session_id,
                            operation_id,
                            update,
                        ),
                    )
                    self._update_camera_operation(
                        device,
                        session_id,
                        operation_id,
                        {
                            "step": result.get("operation", {}).get("step"),
                            "total": result.get("operation", {}).get("total"),
                            "label": "操作完成",
                            "state": "done",
                        },
                    )
                    self.server.camera_cache.patch_from_action(device, result)
                    self.server.camera_cache.trigger(device)
                    result["operation_id"] = operation_id
                    result["operation"] = self._camera_operation_state(device, session_id, operation_id).get("operation")
                    self._send_json(result)
                except Exception as exc:  # noqa: BLE001
                    self._update_camera_operation(
                        device,
                        session_id,
                        operation_id,
                        {
                            "label": str(exc),
                            "state": "error",
                            "detail": action,
                        },
                    )
                    raise
            elif parsed.path == "/api/plan-action":
                # 计划写:仅下发草稿(enable=false)/ 删 / 停用 —— 绝不在网站启用执行。
                device = str(payload.get("device") or "").strip()
                if not device:
                    raise ValueError("device is required")
                self._require_actions_allowed()
                self._send_json(
                    plan_action_response(
                        self.server.config,
                        device_name=device,
                        action=str(payload.get("action") or "").strip(),
                        payload=payload,
                    )
                )
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except BusyError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.CONFLICT)
        except ControlLeaseBusyError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.CONFLICT)
        except PermissionError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.FORBIDDEN)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _actions_allowed(self) -> bool:
        if self.server.read_only:
            return False
        if self.server.allow_remote_actions:
            return True
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def _scan_allowed(self) -> bool:
        return True

    def _require_actions_allowed(self) -> None:
        if not self._actions_allowed():
            raise PermissionError("此入口不允许远程操作 — 请使用可操作入口(端口 8794)")

    def _require_local_write(self) -> None:
        """Gate for write operations that modify local files (scan, warmer, preview generation).

        read_only instances must refuse these operations regardless of allow_remote_actions.
        """
        if self.server.read_only:
            raise PermissionError("只读入口禁止本地写操作 — 请使用可读写入口(端口 8794)")

    def _require_scan_allowed(self) -> None:
        if not self._scan_allowed():
            raise PermissionError("Source scanning is disabled")

    def _require_controller_for_device(self, device_name: str, session_id: str) -> None:
        if self.server.read_only:
            raise PermissionError("只读入口禁止拍摄/写入 — 请使用可操作入口(端口 8794)")
        lease = control_state(self.server.config, device_name, session_id=session_id)
        if not lease.get("held_by_self"):
            raise PermissionError(f"{device_name} 需要主控模式 — 请在顶栏将 监控 切换为 主控")

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        text = self.rfile.read(length).decode("utf-8")
        return json.loads(text)

    def _operation_key(self, device_name: str, session_id: str, operation_id: str) -> str:
        return f"{device_name}\0{session_id}\0{operation_id}"

    def _update_camera_operation(
        self,
        device_name: str,
        session_id: str,
        operation_id: str,
        update: dict[str, Any],
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self.server.camera_operations_lock:
            key = self._operation_key(device_name, session_id, operation_id)
            current = self.server.camera_operations.get(key, {})
            step = update.get("step")
            total = update.get("total")
            current.update(
                {
                    "device": device_name,
                    "session_id": session_id,
                    "operation_id": operation_id,
                    "updated_at": now,
                    "step": step if step is not None else current.get("step", 0),
                    "total": total if total is not None else current.get("total", 1),
                    "label": update.get("label", current.get("label", "")),
                    "state": update.get("state", current.get("state", "running")),
                    "detail": update.get("detail", current.get("detail")),
                    "writes": update.get("writes", current.get("writes", [])),
                }
            )
            current.setdefault("created_at", now)
            self.server.camera_operations[key] = current

            stale_keys = [
                existing_key
                for existing_key, value in self.server.camera_operations.items()
                if time.time() - _parse_iso_seconds(value.get("updated_at")) > 600
            ]
            for stale_key in stale_keys:
                self.server.camera_operations.pop(stale_key, None)

    def _camera_operation_state(
        self,
        device_name: str,
        session_id: str,
        operation_id: str,
    ) -> dict[str, Any]:
        with self.server.camera_operations_lock:
            if operation_id:
                operation = self.server.camera_operations.get(
                    self._operation_key(device_name, session_id, operation_id)
                )
            else:
                operation = None
                prefix = f"{device_name}\0{session_id}\0"
                for key, value in self.server.camera_operations.items():
                    if key.startswith(prefix):
                        if operation is None or str(value.get("updated_at", "")) > str(operation.get("updated_at", "")):
                            operation = value
            return {
                "ok": True,
                "device": device_name,
                "session_id": session_id,
                "operation_id": operation_id,
                "operation": operation,
            }

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(
        self,
        path: Path,
        content_type: str,
        download_name: str | None = None,
        cache_seconds: int = 0,
        allow_gzip: bool = False,
    ) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        encoding: str | None = None
        # 16bit 原始帧很大(~116MB):客户端支持时 gzip 后再发(~46MB),浏览器透明解压
        if allow_gzip and "gzip" in (self.headers.get("Accept-Encoding") or "").lower():
            body = gzip.compress(body, 1)
            encoding = "gzip"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if encoding:
            self.send_header("Content-Encoding", encoding)
        if cache_seconds > 0:
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        elif content_type.startswith(("text/html", "application/javascript")):
            # 页面与脚本禁止启发式缓存,部署即生效(图像类响应不受影响)
            self.send_header("Cache-Control", "no-store")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_download_file(self, path: Path) -> None:
        """单文件原始素材下载:带 Content-Length,1MB 分块流式发送(不整文件入内存)。"""
        try:
            size = path.stat().st_size
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header(
            "Content-Disposition", f'attachment; filename="{_safe_attachment_name(path.name)}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _send_materials_zip(self, files: list, zipname: str) -> None:
        """多选/文件夹打包下载:STORED 流式 ZIP,大小未知靠连接关闭界定(HTTP/1.0 兼容),
        逐文件读发不占内存,单个文件读失败则跳过保住其余。"""
        if not files:
            self._send_json({"ok": False, "error": "没有可下载的文件"}, HTTPStatus.NOT_FOUND)
            return
        # 大小未知 → 靠连接关闭界定下载完成(HTTP/1.0),显式置 close 确保发完即断
        self.close_connection = True
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{zipname}"')
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        zf = zipfile.ZipFile(_StreamWriter(self.wfile), "w", zipfile.ZIP_STORED, allowZip64=True)
        try:
            for path, arc in files:
                try:
                    zf.write(str(path), arc)
                except OSError:
                    continue
        finally:
            try:
                zf.close()
                self.wfile.flush()
            except OSError:
                pass

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class BusyError(RuntimeError):
    pass


def _parse_iso_seconds(value: Any) -> float:
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def start_backup(config: AppConfig, payload: dict[str, Any]) -> dict[str, Any]:
    lock = read_lock(config.project.lock_file)
    if lock.get("active") and lock.get("pid_alive") is not False:
        raise BusyError(f"Backup already running, pid={lock.get('pid')}")

    device = payload.get("device")
    source_label = DASHBOARD_SOURCE_LABEL
    dry_run = bool(payload.get("dry_run", True))
    force_lock = bool(payload.get("force_lock", False))

    args = [
        sys.executable,
        "-B",
        "-m",
        "asiairbridge",
        "--config",
        str(config.path),
        "backup",
        "--dry-run" if dry_run else "--no-dry-run",
    ]
    if device:
        args.extend(["--device", str(device)])
    if source_label:
        args.extend(["--source-label", str(source_label)])
    if force_lock:
        args.append("--force-lock")

    process_log_dir = config.state_path() / "web-processes"
    process_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = process_log_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(config.root / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    stdout = log_path.open("a", encoding="utf-8", errors="replace")
    try:
        proc = subprocess.Popen(
            args,
            cwd=config.root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
    finally:
        stdout.close()

    return {
        "ok": True,
        "pid": proc.pid,
        "dry_run": dry_run,
        "device": device,
        "source_label": source_label,
        "process_log": str(log_path),
    }
