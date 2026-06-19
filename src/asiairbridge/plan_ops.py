from __future__ import annotations

import copy
import threading
import time
from datetime import datetime
from typing import Any

from .config import AppConfig, Device
from .rpc import IMAGER_PORT, asiair_rpc

# Subsystems whose {is_working} flags get_app_state reports — surfaced so the page
# can show what the box is doing besides exposing (goto / focus / flip / stack …).
_BUSY_KEYS = (
    "auto_goto", "auto_focus", "merid_flip", "stack", "pa", "pa_3p",
    "find_star", "avi_record", "batch_stack", "annotate", "solve",
)


class PlanMonitor:
    """Per-device read-only poller for the planned-imaging page.

    The plan tree (``get_plan`` / ``list_plan``) changes slowly and is sizeable, so
    it is refreshed on a long interval; the live capture progress (``get_app_state``)
    is refreshed often. Both keep their last good value if a poll loses the busy
    4700 priority queue, so an actively-exposing box still shows fresh-enough data.
    Strictly read-only — never sends a plan/sequence/exposure command.
    """

    def __init__(self, config: AppConfig, app_interval: float = 4.0, plan_interval: float = 22.0) -> None:
        self.config = config
        self.app_interval = app_interval
        self.plan_interval = plan_interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._state: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        self._threads = []
        for device in self.config.enabled_devices():
            self._state.setdefault(device.name, {})
            app_thread = threading.Thread(
                target=self._run_app_loop,
                args=(device,),
                name=f"asiair-plan-app-{device.name}",
                daemon=True,
            )
            plan_thread = threading.Thread(
                target=self._run_plan_loop,
                args=(device,),
                name=f"asiair-plan-tree-{device.name}",
                daemon=True,
            )
            app_thread.start()
            plan_thread.start()
            self._threads.append(app_thread)
            self._threads.append(plan_thread)

    def stop(self) -> None:
        self._stop.set()

    def get(self, device_name: str | None) -> dict[str, Any]:
        device = self._select(device_name)
        if device is None:
            return {"ok": True, "device": {"name": device_name}, "connected": False,
                    "plans": [], "plan_list": [], "error": "unknown device"}
        with self._lock:
            state = copy.deepcopy(self._state.get(device.name, {}))
        now = time.time()
        capture_at = state.get("capture_at")
        plan_at = state.get("plan_at")
        return {
            "ok": True,
            "device": {"name": device.name, "ip": device.ip},
            "connected": bool(state.get("connected")),
            "page": state.get("page"),
            "capture": state.get("capture"),
            "busy": state.get("busy") or {},
            "plan_list": state.get("plan_list") or [],
            "plans": state.get("plans") or [],
            "capture_age": round(now - capture_at, 1) if capture_at else None,
            "plan_age": round(now - plan_at, 1) if plan_at else None,
            "snapshot_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _select(self, name: str | None) -> Device | None:
        for device in self.config.enabled_devices():
            if device.name == name:
                return device
        if name:
            return None
        try:
            return self.config.default_device()
        except Exception:  # noqa: BLE001
            return None

    def _run_app_loop(self, device: Device) -> None:
        while not self._stop.is_set():
            self._poll_app(device)
            self._stop.wait(self.app_interval)

    def _run_plan_loop(self, device: Device) -> None:
        # Stagger plan-tree RPCs so the first slow poll does not contend with app state.
        self._stop.wait(self.app_interval)
        while not self._stop.is_set():
            self._poll_plan(device)
            self._stop.wait(self.plan_interval)

    def _rpc(self, device: Device, method: str, timeout: float = 4.0) -> Any:
        try:
            response = asiair_rpc(
                device.ip,
                method,
                port=IMAGER_PORT,
                timeout_seconds=timeout,
                priority="background",
                queue_timeout_seconds=3.0,
            )
        except Exception:  # noqa: BLE001
            return None
        if isinstance(response, dict) and response.get("code") in (0, None):
            return response.get("result")
        return None

    def _poll_app(self, device: Device) -> None:
        app = self._rpc(device, "get_app_state", 4.0)
        with self._lock:
            state = self._state.setdefault(device.name, {})
            if isinstance(app, dict):
                state["capture"] = app.get("capture")
                state["page"] = app.get("page")
                state["busy"] = {k: bool(app[k].get("is_working"))
                                 for k in _BUSY_KEYS
                                 if isinstance(app.get(k), dict) and "is_working" in app[k]}
                state["connected"] = True
                state["capture_at"] = time.time()
            else:
                state["connected"] = False

    def _poll_plan(self, device: Device) -> None:
        plan_list = self._rpc(device, "list_plan", 4.0)
        plans = self._rpc(device, "get_plan", 6.0)
        with self._lock:
            state = self._state.setdefault(device.name, {})
            if isinstance(plan_list, list):
                state["plan_list"] = plan_list
            if isinstance(plans, list):
                state["plans"] = plans
                state["plan_at"] = time.time()


def plan_action_response(
    config: AppConfig,
    device_name: str | None,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """计划写操作 —— 仅 deploy(下发草稿)/ delete(删) / disable(停用)。

    安全红线:网站只下发 **enable=False 的草稿**(set_plan 传未占用的新 id = 新建,
    绝不覆盖现有计划),并支持删除、停用。**绝不在此启用执行(enable=True)** —— 启用一个
    带 dusk 定时的计划会让盒子在昏影无人值守自动 goto+拍摄;启用必须在 ASIAIR App 内、
    确认开顶后由人手动操作。写方法(set_plan/delete_plan/import_plan)均为抓包实测,
    回包 {result:0,code:0}。
    """
    from .camera_ops import _select_device  # 复用设备选取(同一 enabled_devices)

    device = _select_device(config, device_name)
    request_id = 90_000

    def rpc(method: str, params: Any | None = None, ok_codes: tuple[int, ...] = (0,),
            timeout_seconds: float = 10.0) -> Any:
        nonlocal request_id
        request_id += 1
        try:
            response = asiair_rpc(
                device.ip, method, params=params, request_id=request_id,
                port=IMAGER_PORT, timeout_seconds=timeout_seconds, priority="write",
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"{method} {params!r} 发送失败: {exc}") from exc
        if response.get("code") not in ok_codes:
            raise RuntimeError(f"{method} 失败 code={response.get('code')}: {response.get('error')}")
        return response.get("result")

    action = (action or "").strip().lower()

    if action == "deploy":
        plan = payload.get("plan")
        if not isinstance(plan, dict):
            raise ValueError("deploy 需要 plan(对象)")
        plan = copy.deepcopy(plan)
        existing = rpc("list_plan", timeout_seconds=6.0) or []
        used = {p.get("id") for p in existing
                if isinstance(p, dict) and isinstance(p.get("id"), int)}
        new_id = (max(used) + 1) if used else 1
        while new_id in used:
            new_id += 1
        plan["id"] = new_id
        plan["enable"] = False  # 安全红线:下发为草稿,绝不自动执行
        rpc("set_plan", params=[plan], timeout_seconds=12.0)
        return {
            "ok": True,
            "action": "deploy",
            "plan_id": new_id,
            "plan_name": plan.get("plan_name"),
            "enable": False,
            "targets": len(plan.get("targets") or []),
            "note": "已作为草稿下发(enable=false,不会自动执行);请在 ASIAIR App 审核,确认开顶后再启用。",
        }

    if action in ("delete", "disable"):
        try:
            pid = int(payload.get("plan_id"))
        except (TypeError, ValueError):
            raise ValueError(f"{action} 需要 plan_id(整数)")
        if action == "delete":
            rpc("delete_plan", params=[{"plan_id": pid}], timeout_seconds=12.0)
            return {"ok": True, "action": "delete", "plan_id": pid}
        rpc("import_plan", params=[{"id": pid, "enable": False}], timeout_seconds=12.0)
        return {"ok": True, "action": "disable", "plan_id": pid, "enable": False}

    raise ValueError(
        f"未知或不允许的计划操作: {action!r} —— 网站仅支持 deploy/delete/disable;"
        "启用执行(enable=true)须在 App 内、确认开顶后手动操作。"
    )
