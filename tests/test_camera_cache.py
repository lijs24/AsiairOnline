"""P3-3: Unit tests for CameraStateCache — failure merging and patch_from_action.

All tests run without a real device (no network, no RPC).
"""
from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Stub moderngl which camera_cache doesn't need but image_preview may pull in
for _m in ("moderngl",):
    if _m not in sys.modules:
        sys.modules[_m] = types.ModuleType(_m)

from asiairbridge.config import AppConfig, BackupSettings, Device, ProjectSettings  # noqa: E402
from asiairbridge.camera_cache import CameraStateCache  # noqa: E402


def _make_config(tmp_path: Path, device_name: str = "cam1") -> AppConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "state").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)
    proj = ProjectSettings(
        timezone="UTC",
        destination_root=tmp_path / "dest",
        logs_dir=tmp_path / "logs",
        state_dir=tmp_path / "state",
        lock_file=tmp_path / "state" / "lock",
        robocopy_threads=2,
    )
    backup = BackupSettings(
        dry_run_default=False,
        copy_empty_dirs=False,
        retry_count=0,
        retry_wait_seconds=0,
        job_timeout_hours=1,
        smb_port=445,
        exclude_dirs=(),
        exclude_files=(),
        source_roots=(),
    )
    device = Device(name=device_name, ip="192.0.2.1", enabled=True)
    return AppConfig(
        path=tmp_path / "config.json",
        root=tmp_path,
        project=proj,
        backup=backup,
        devices=(device,),
    )


@pytest.fixture()
def config(tmp_path):
    return _make_config(tmp_path)


# ---------------------------------------------------------------------------
# Helper: patch control_state so CameraStateCache doesn't need a running server
# ---------------------------------------------------------------------------
_LEASE_OK = {"held_by_self": False, "controller": None, "role": "monitor", "ok": True}


class TestCameraStateCacheGet:
    def test_get_returns_warming_when_empty(self, config):
        """Cache with no stored payload returns a partial 'warming' response."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            result = cache.get("cam1", session_id=None)
        assert result.get("ok") is True
        assert result.get("partial") is True
        cache_meta = result.get("cache", {})
        assert cache_meta.get("status") == "warming"

    def test_get_after_store_returns_payload(self, config):
        """store() followed by get() returns the stored payload."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            payload = {
                "ok": True,
                "partial": False,
                "errors": [],
                "snapshot_at": "2026-06-17T12:00:00",
                "device": {"name": "cam1", "ip": "192.0.2.1"},
                "app": {"page": None, "capture_state": "IDLE", "capture_working": False, "exposure_mode": None},
                "camera": {"name": "ZWO ASI2600MM"},
                "exposure": {"us": 30_000_000, "seconds": 30.0, "bin": 1},
                "controls": {},
                "subframe": {"width": None, "height": None, "x": None, "y": None},
                "image": {"generated_at": None, "age_seconds": None, "refreshed": False,
                          "image_id": None, "width": None, "height": None,
                          "exposure_ms": None, "bin": None},
            }
            cache.store(payload)
            result = cache.get("cam1", session_id=None)
        assert result["camera"]["name"] == "ZWO ASI2600MM"
        assert result["cache"]["from_cache"] is True
        assert result["cache"]["status"] in ("ready", "partial")


class TestPatchFromAction:
    def test_patch_updates_exposure(self, config):
        """patch_from_action with set_camera_exp_and_bin write should update exposure field."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            # Prime cache with an initial payload
            initial = {
                "ok": True,
                "partial": False,
                "errors": [],
                "snapshot_at": "2026-06-17T12:00:00",
                "device": {"name": "cam1", "ip": "192.0.2.1"},
                "app": {"page": None, "capture_state": "IDLE", "capture_working": False, "exposure_mode": None},
                "camera": {"name": "ASI2600"},
                "exposure": {"us": 5_000_000, "seconds": 5.0, "bin": 1},
                "controls": {},
                "subframe": {"width": None, "height": None, "x": None, "y": None},
                "image": {"generated_at": None, "age_seconds": None, "refreshed": False,
                          "image_id": None, "width": None, "height": None,
                          "exposure_ms": None, "bin": None},
            }
            cache.store(initial)

            action_result = {
                "ok": True,
                "writes": [
                    {
                        "method": "set_camera_exp_and_bin",
                        "params": [{"exposure": 10_000_000, "bin": 2}],
                    }
                ],
            }
            cache.patch_from_action("cam1", action_result)
            result = cache.get("cam1", session_id=None)

        assert result["exposure"]["us"] == 10_000_000
        assert result["exposure"]["seconds"] == pytest.approx(10.0)
        assert result["exposure"]["bin"] == 2

    def test_patch_no_matching_write_leaves_cache_unchanged(self, config):
        """patch_from_action with unrecognised write method must not corrupt the cache."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            initial = {
                "ok": True, "partial": False, "errors": [],
                "snapshot_at": "2026-06-17T12:00:00",
                "device": {"name": "cam1", "ip": "192.0.2.1"},
                "app": {"page": None, "capture_state": "IDLE", "capture_working": False, "exposure_mode": None},
                "camera": {"name": "ASI2600"},
                "exposure": {"us": 3_000_000, "seconds": 3.0, "bin": 1},
                "controls": {},
                "subframe": {"width": None, "height": None, "x": None, "y": None},
                "image": {"generated_at": None, "age_seconds": None, "refreshed": False,
                          "image_id": None, "width": None, "height": None,
                          "exposure_ms": None, "bin": None},
            }
            cache.store(initial)
            cache.patch_from_action("cam1", {"ok": True, "writes": [{"method": "unknown_rpc"}]})
            result = cache.get("cam1", session_id=None)

        assert result["exposure"]["us"] == 3_000_000

    def test_patch_on_empty_cache_for_unknown_device_does_not_raise(self, config):
        """patch_from_action on a device not in config should silently return."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            # "ghost-device" is not in config.devices
            try:
                cache.patch_from_action("ghost-device", {"ok": True, "writes": []})
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"patch_from_action raised unexpectedly: {exc}")

    def test_store_ignores_payload_with_missing_device_name(self, config):
        """store() with no device name field must not crash."""
        with patch("asiairbridge.camera_cache.control_state", return_value=_LEASE_OK):
            cache = CameraStateCache(config, interval_seconds=9999)
            try:
                cache.store({"ok": True})  # no "device" key
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"store() raised unexpectedly: {exc}")
