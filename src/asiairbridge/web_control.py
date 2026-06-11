from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import AppConfig

ROLE_MONITOR = "monitor"
ROLE_CONTROLLER = "controller"
LEASE_SECONDS = 45

_STATE_LOCK = threading.Lock()


class ControlLeaseBusyError(RuntimeError):
    """Raised when another session currently holds controller access."""


def control_state(config: AppConfig, device_name: str, session_id: str | None = None) -> dict[str, Any]:
    now = datetime.now()
    with _STATE_LOCK:
        payload = _load_state(_state_path(config))
        changed = _prune_expired(payload, now)
        device_state = payload.get("devices", {}).get(device_name)
        if changed:
            _save_state(_state_path(config), payload)
    return _describe_state(device_name, device_state, session_id=session_id, now=now)


def update_control_role(
    config: AppConfig,
    *,
    device_name: str,
    session_id: str,
    client_ip: str,
    role: str,
    session_label: str | None = None,
) -> dict[str, Any]:
    normalized_role = str(role or ROLE_MONITOR).strip().lower()
    if normalized_role not in {ROLE_MONITOR, ROLE_CONTROLLER}:
        raise ValueError(f"Unsupported role: {role}")
    if not session_id:
        raise ValueError("session_id is required")

    now = datetime.now()
    path = _state_path(config)
    with _STATE_LOCK:
        payload = _load_state(path)
        _prune_expired(payload, now)
        devices = payload.setdefault("devices", {})
        current = devices.get(device_name)
        holder = current.get("controller") if isinstance(current, dict) else None

        if normalized_role == ROLE_MONITOR:
            if holder and holder.get("session_id") == session_id:
                devices.pop(device_name, None)
        else:
            if holder and holder.get("session_id") != session_id:
                raise ControlLeaseBusyError(
                    f"{device_name} 主控已由 {holder.get('session_label') or holder.get('client_ip') or '其他会话'} 占用"
                )
            claimed_at = holder.get("claimed_at") if isinstance(holder, dict) else None
            devices[device_name] = {
                "controller": {
                    "session_id": session_id,
                    "session_label": _safe_label(session_label),
                    "client_ip": client_ip,
                    "claimed_at": claimed_at or now.isoformat(timespec="seconds"),
                    "renewed_at": now.isoformat(timespec="seconds"),
                    "expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat(timespec="seconds"),
                }
            }

        payload["updated_at"] = now.isoformat(timespec="seconds")
        _save_state(path, payload)
        device_state = payload.get("devices", {}).get(device_name)
    return _describe_state(device_name, device_state, session_id=session_id, now=now)


def _describe_state(
    device_name: str,
    device_state: dict[str, Any] | None,
    *,
    session_id: str | None,
    now: datetime,
) -> dict[str, Any]:
    holder = None
    held_by_self = False
    if isinstance(device_state, dict) and isinstance(device_state.get("controller"), dict):
        controller = device_state["controller"]
        holder = {
            "session_id": controller.get("session_id"),
            "session_label": controller.get("session_label"),
            "client_ip": controller.get("client_ip"),
            "claimed_at": controller.get("claimed_at"),
            "renewed_at": controller.get("renewed_at"),
            "expires_at": controller.get("expires_at"),
            "display_name": _display_name(
                controller.get("session_label"),
                controller.get("client_ip"),
            ),
        }
        held_by_self = bool(session_id and controller.get("session_id") == session_id)

    return {
        "ok": True,
        "device": device_name,
        "lease_seconds": LEASE_SECONDS,
        "server_time": now.isoformat(timespec="seconds"),
        "controller": holder,
        "held_by_self": held_by_self,
        "role": ROLE_CONTROLLER if held_by_self else ROLE_MONITOR,
        "available": holder is None or held_by_self,
    }


def _safe_label(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:80]


def _display_name(label: Any, client_ip: Any) -> str:
    text_label = str(label or "").strip()
    text_ip = str(client_ip or "").strip()
    if text_label and text_ip:
        return f"{text_label} @ {text_ip}"
    if text_label:
        return text_label
    if text_ip:
        return text_ip
    return "未知会话"


def _state_path(config: AppConfig) -> Path:
    return config.state_path() / "web" / "control-roles.json"


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"devices": {}, "updated_at": None}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        return {"devices": {}, "updated_at": None}
    if not isinstance(data.get("devices"), dict):
        data["devices"] = {}
    return data


def _save_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    temp_path.replace(path)


def _prune_expired(payload: dict[str, Any], now: datetime) -> bool:
    changed = False
    devices = payload.setdefault("devices", {})
    expired: list[str] = []
    for device_name, device_state in devices.items():
        controller = device_state.get("controller") if isinstance(device_state, dict) else None
        expires_at = controller.get("expires_at") if isinstance(controller, dict) else None
        if not expires_at:
            expired.append(device_name)
            continue
        try:
            expiry = datetime.fromisoformat(str(expires_at))
        except ValueError:
            expired.append(device_name)
            continue
        if expiry <= now:
            expired.append(device_name)
    for device_name in expired:
        devices.pop(device_name, None)
        changed = True
    return changed
