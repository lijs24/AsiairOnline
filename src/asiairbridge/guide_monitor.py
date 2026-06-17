from __future__ import annotations

import json
import math
import socket
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any

from .config import AppConfig, Device
from .rpc import GUIDER_PORT, IMAGER_PORT, asiair_rpc

# Read-only snapshot methods issued on the guider endpoint (port 4400, PHD2
# protocol). None of these mutate device state.
_SNAPSHOT_METHODS_4400 = (
    "get_app_state",
    "get_calibrated",
    "get_paused",
    "get_connected",
    "get_pixel_scale",
    "get_exposure",
    "get_lock_position",
    "get_dec_guide_mode",
    "get_search_region",
)

_MAX_STEPS = 3600     # live ring buffer of recent GuideStep events (~1 h at 1 Hz)
_CURVE_POINTS = 3600  # points handed to the live frontend (full buffer; frontend windows it by time)
_RMS_WINDOW = 100     # recent steps used for the server-side rolling RMS (frontend recomputes per window)
_LOG_DOWNSAMPLE = 2000  # max points returned when reading back a whole night's log


class GuideMonitor:
    """Per-device daemon that holds a persistent connection to the ASIAIR
    guider endpoint (port 4400, PHD2-style protocol).

    It listens for streamed ``GuideStep`` events to build the live guiding
    curve and RMS, and periodically issues *read-only* snapshot requests for
    the guiding settings (state, pixel scale, exposure, lock position, …) on
    the same connection. It never issues a guide/dither/calibrate/set command —
    this is a monitor, not a controller.
    """

    def __init__(
        self,
        config: AppConfig,
        snapshot_interval: float = 4.0,
        reconnect_seconds: float = 3.0,
    ) -> None:
        self.config = config
        self.snapshot_interval = snapshot_interval
        self.reconnect_seconds = reconnect_seconds
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._steps: dict[str, deque] = {}
        self._settings: dict[str, dict[str, Any]] = {}
        self._meta: dict[str, dict[str, Any]] = {}
        self._logfh: dict[str, tuple[str, Any]] = {}  # device -> (night_date, open append handle)

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        self._threads = []
        for device in self.config.enabled_devices():
            self._steps.setdefault(device.name, deque(maxlen=_MAX_STEPS))
            self._settings.setdefault(device.name, {})
            self._meta.setdefault(device.name, {})
            thread = threading.Thread(
                target=self._run_device,
                args=(device,),
                name=f"asiair-guide-{device.name}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        for state in list(self._logfh.values()):
            try:
                state[1].close()
            except OSError:
                pass

    def get_all(self) -> dict[str, Any]:
        devices: dict[str, dict[str, Any]] = {}
        for device in self.config.enabled_devices():
            devices[device.name] = self._device_view(device)
        return {
            "ok": True,
            "snapshot_at": datetime.now().isoformat(timespec="seconds"),
            "devices": devices,
        }

    def get_one(self, device_name: str) -> dict[str, Any]:
        """Single-device view — the live page only ever shows one box, so this
        keeps the 1 h curve payload to that box instead of all of them."""
        snapshot = datetime.now().isoformat(timespec="seconds")
        for device in self.config.enabled_devices():
            if device.name == device_name:
                return {"ok": True, "snapshot_at": snapshot,
                        "devices": {device.name: self._device_view(device)}}
        return {"ok": True, "snapshot_at": snapshot, "devices": {}}

    def _device_view(self, device: Device) -> dict[str, Any]:
        with self._lock:
            steps = list(self._steps.get(device.name, ()))
            settings = dict(self._settings.get(device.name, {}))
            meta = dict(self._meta.get(device.name, {}))

        pixel_scale = settings.get("pixel_scale")
        rms = _compute_rms(steps[-_RMS_WINDOW:], pixel_scale)
        curve = [
            {
                "wt": step.get("wt"),
                "ra": step.get("ra"),
                "dec": step.get("dec"),
                "dx": step.get("dx"),
                "dy": step.get("dy"),
                "snr": step.get("snr"),
            }
            for step in steps[-_CURVE_POINTS:]
        ]
        updated_at = meta.get("updated_at")
        connected = meta.get("connected_at") is not None and meta.get("error") is None
        age = None if updated_at is None else max(0.0, time.time() - updated_at)
        return {
            "device": {"name": device.name, "ip": device.ip},
            "connected": connected,
            "state": settings.get("state"),
            "error": meta.get("error"),
            "rms": rms,
            "last": steps[-1] if steps else None,
            "curve": curve,
            "settings": {
                "pixel_scale": pixel_scale,
                "exposure_ms": settings.get("exposure_ms"),
                "dec_guide_mode": settings.get("dec_guide_mode"),
                "search_region": settings.get("search_region"),
                "calibrated": settings.get("calibrated"),
                "paused": settings.get("paused"),
                "lock_position": settings.get("lock_position"),
                "dither": settings.get("dither"),
                "camera": settings.get("camera"),
                "mount": settings.get("mount"),
            },
            "updated_at": (
                datetime.fromtimestamp(updated_at).isoformat(timespec="seconds")
                if updated_at is not None
                else None
            ),
            "age_seconds": round(age, 1) if age is not None else None,
        }

    def _run_device(self, device: Device) -> None:
        while not self._stop.is_set():
            try:
                self._stream(device)
            except Exception as exc:  # noqa: BLE001
                self._set_error(device.name, str(exc))
            if self._stop.is_set():
                break
            self._stop.wait(self.reconnect_seconds)

    def _stream(self, device: Device) -> None:
        with socket.create_connection((device.ip, GUIDER_PORT), timeout=5.0) as sock:
            sock.settimeout(1.0)
            with self._lock:
                prior = self._meta.get(device.name, {})
                self._meta[device.name] = {
                    "connected_at": time.time(),
                    "updated_at": prior.get("updated_at"),
                    "error": None,
                }
            buffer = b""
            pending: dict[int, str] = {}
            req_id = 90000
            last_snapshot = 0.0
            last_dither = 0.0
            while not self._stop.is_set():
                now = time.monotonic()
                if now - last_snapshot >= self.snapshot_interval:
                    last_snapshot = now
                    for method in _SNAPSHOT_METHODS_4400:
                        req_id += 1
                        pending[req_id] = method
                        try:
                            sock.sendall(
                                json.dumps(
                                    {"id": req_id, "method": method},
                                    separators=(",", ":"),
                                ).encode("utf-8")
                                + b"\r\n"
                            )
                        except OSError:
                            return
                    if now - last_dither >= self.snapshot_interval * 2:
                        last_dither = now
                        self._snapshot_dither(device)
                    # keep only the most recent pending ids to bound memory
                    if len(pending) > 64:
                        for stale in sorted(pending)[:-32]:
                            pending.pop(stale, None)
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    continue
                if not chunk:
                    return
                buffer += chunk
                lines = buffer.split(b"\n")
                buffer = lines[-1]
                for raw in lines[:-1]:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        message = json.loads(raw.decode("utf-8", "replace"))
                    except json.JSONDecodeError:
                        continue
                    if isinstance(message, dict):
                        self._handle(device.name, message, pending)

    def _handle(self, name: str, message: dict[str, Any], pending: dict[int, str]) -> None:
        if message.get("Event") == "GuideStep":
            self._add_step(name, message)
            return
        message_id = message.get("id")
        if message_id in pending:
            method = pending.pop(message_id)
            if message.get("code") in (0, None):
                self._apply_setting(name, method, message.get("result"))
            self._touch(name)

    def _add_step(self, name: str, message: dict[str, Any]) -> None:
        step = {
            "t": _as_float(message.get("Time")) or time.time(),
            "wt": time.time(),
            "frame": message.get("Frame"),
            "dx": _as_float(message.get("dx")),
            "dy": _as_float(message.get("dy")),
            "ra": _as_float(message.get("RADistanceRaw")),
            "dec": _as_float(message.get("DECDistanceRaw")),
            "snr": _as_float(message.get("SNR")),
            "star_mass": _as_float(message.get("StarMass")),
        }
        with self._lock:
            self._steps.setdefault(name, deque(maxlen=_MAX_STEPS)).append(step)
        self._append_log(name, step)
        self._touch(name)

    def _apply_setting(self, name: str, method: str, result: Any) -> None:
        with self._lock:
            settings = self._settings.setdefault(name, {})
            if method == "get_app_state":
                settings["state"] = result
            elif method == "get_calibrated":
                settings["calibrated"] = result
            elif method == "get_paused":
                settings["paused"] = result
            elif method == "get_pixel_scale":
                settings["pixel_scale"] = _as_float(result)
            elif method == "get_exposure":
                settings["exposure_ms"] = result
            elif method == "get_lock_position":
                settings["lock_position"] = result
            elif method == "get_dec_guide_mode":
                settings["dec_guide_mode"] = result
            elif method == "get_search_region":
                settings["search_region"] = result
            elif method == "get_connected" and isinstance(result, dict):
                camera = result.get("camera")
                settings["camera"] = camera.get("name") if isinstance(camera, dict) else None
                settings["mount"] = result.get("mount_name")

    def _snapshot_dither(self, device: Device) -> None:
        try:
            response = asiair_rpc(
                device.ip,
                "get_dither",
                port=IMAGER_PORT,
                timeout_seconds=2.0,
                priority="background",
            )
        except Exception:  # noqa: BLE001
            return
        if isinstance(response, dict) and response.get("code") in (0, None):
            with self._lock:
                self._settings.setdefault(device.name, {})["dither"] = response.get("result")

    def _touch(self, name: str) -> None:
        with self._lock:
            meta = self._meta.setdefault(name, {})
            meta["updated_at"] = time.time()
            meta["error"] = None

    def _set_error(self, name: str, error: str) -> None:
        with self._lock:
            meta = self._meta.setdefault(name, {})
            meta["error"] = error
            meta["connected_at"] = None

    # ── per-night persistence ───────────────────────────────────────────
    def _log_dir(self, device_name: str):
        return self.config.state_path() / "guide-log" / device_name

    @staticmethod
    def _unsafe(token: str) -> bool:
        return (not token) or "/" in token or "\\" in token or ".." in token

    def night_file(self, device_name: str, date: str):
        """Validated path to a night's log file, or None. Guards against path escapes."""
        if self._unsafe(str(device_name)) or self._unsafe(str(date)):
            return None
        path = self._log_dir(device_name) / f"{date}.jsonl"
        return path if path.is_file() else None

    def _append_log(self, name: str, step: dict[str, Any]) -> None:
        """Append one GuideStep to the current night's JSONL log. A "night" runs
        noon→noon so a session crossing midnight stays in one file. Logging must
        never raise into the monitor loop."""
        try:
            night = (datetime.now() - timedelta(hours=12)).date().isoformat()
            state = self._logfh.get(name)
            if state is None or state[0] != night:
                if state is not None:
                    try:
                        state[1].close()
                    except OSError:
                        pass
                path = self._log_dir(name) / f"{night}.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                state = (night, path.open("a", encoding="utf-8"))
                self._logfh[name] = state
            state[1].write(json.dumps({
                "wt": round(step.get("wt") or time.time(), 1),
                "ra": step.get("ra"),
                "dec": step.get("dec"),
                "dx": step.get("dx"),
                "dy": step.get("dy"),
                "snr": step.get("snr"),
            }, separators=(",", ":")) + "\n")
            state[1].flush()
        except Exception:  # noqa: BLE001
            pass

    def list_nights(self, device_name: str) -> dict[str, Any]:
        if self._unsafe(str(device_name)):
            return {"ok": True, "device": device_name, "nights": []}
        directory = self._log_dir(device_name)
        nights: list[dict[str, Any]] = []
        if directory.is_dir():
            for path in sorted(directory.glob("*.jsonl"), reverse=True):
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                nights.append({"date": path.stem, "bytes": size})
        return {"ok": True, "device": device_name, "nights": nights}

    def read_night(self, device_name: str, date: str, max_points: int = _LOG_DOWNSAMPLE) -> dict[str, Any]:
        path = self.night_file(device_name, date)
        if path is None:
            return {"ok": False, "error": "no log for that night", "points": []}
        rows: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:
            return {"ok": False, "error": str(exc), "points": []}
        ras = [r["ra"] for r in rows if isinstance(r.get("ra"), (int, float))]
        decs = [r["dec"] for r in rows if isinstance(r.get("dec"), (int, float))]
        rms = None
        if ras and decs:
            ra_rms = math.sqrt(sum(v * v for v in ras) / len(ras))
            dec_rms = math.sqrt(sum(v * v for v in decs) / len(decs))
            rms = {
                "ra": round(ra_rms, 3),
                "dec": round(dec_rms, 3),
                "total": round(math.sqrt(ra_rms * ra_rms + dec_rms * dec_rms), 3),
                "n": min(len(ras), len(decs)),
            }
        total = len(rows)
        if max_points > 0 and total > max_points:
            stride = total / max_points
            points = [rows[int(index * stride)] for index in range(max_points)]
        else:
            points = rows
        return {
            "ok": True,
            "date": date,
            "total": total,
            "shown": len(points),
            "start": rows[0].get("wt") if rows else None,
            "end": rows[-1].get("wt") if rows else None,
            "rms": rms,
            "points": points,
        }


def _compute_rms(steps: list[dict[str, Any]], pixel_scale: Any) -> dict[str, Any]:
    ras = [step["ra"] for step in steps if isinstance(step.get("ra"), (int, float))]
    decs = [step["dec"] for step in steps if isinstance(step.get("dec"), (int, float))]
    if not ras or not decs:
        return {
            "n": 0,
            "ra_px": None, "dec_px": None, "total_px": None,
            "ra_arcsec": None, "dec_arcsec": None, "total_arcsec": None,
        }
    # RADistanceRaw/DECDistanceRaw are ALREADY in arcsec (PHD2 has applied the
    # pixel scale). The RMS of them is therefore arcsec; pixels = arcsec / scale.
    ra_rms = math.sqrt(sum(value * value for value in ras) / len(ras))
    dec_rms = math.sqrt(sum(value * value for value in decs) / len(decs))
    total = math.sqrt(ra_rms * ra_rms + dec_rms * dec_rms)
    scale = pixel_scale if isinstance(pixel_scale, (int, float)) and pixel_scale > 0 else None
    return {
        "n": min(len(ras), len(decs)),
        "ra_arcsec": round(ra_rms, 3),
        "dec_arcsec": round(dec_rms, 3),
        "total_arcsec": round(total, 3),
        "ra_px": round(ra_rms / scale, 3) if scale else None,
        "dec_px": round(dec_rms / scale, 3) if scale else None,
        "total_px": round(total / scale, 3) if scale else None,
    }


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
