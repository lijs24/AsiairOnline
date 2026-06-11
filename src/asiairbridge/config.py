from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("config/devices.json")
WINDOWS_RESERVED_CHARS = re.compile(r'[<>:"/\\|?*]+')


class ConfigError(ValueError):
    """Raised when the project configuration is invalid."""


@dataclass(frozen=True)
class Device:
    name: str
    ip: str
    enabled: bool = True
    source_roots: tuple["SourceRoot", ...] | None = None


@dataclass(frozen=True)
class SourceRoot:
    label: str
    path_template: str
    enabled: bool = True

    def render(self, device: Device) -> Path:
        return Path(self.path_template.format(ip=device.ip, name=device.name))

    @property
    def safe_label(self) -> str:
        cleaned = WINDOWS_RESERVED_CHARS.sub("_", self.label).strip(" .")
        return cleaned or "source"


@dataclass(frozen=True)
class ProjectSettings:
    timezone: str
    destination_root: Path
    logs_dir: Path
    state_dir: Path
    lock_file: Path
    robocopy_threads: int
    default_device: str | None = None
    private_path_prefixes: tuple[Path, ...] = ()


@dataclass(frozen=True)
class BackupSettings:
    dry_run_default: bool
    copy_empty_dirs: bool
    retry_count: int
    retry_wait_seconds: int
    smb_port: int
    exclude_dirs: tuple[str, ...]
    exclude_files: tuple[str, ...]
    source_roots: tuple[SourceRoot, ...]


@dataclass(frozen=True)
class AppConfig:
    path: Path
    root: Path
    project: ProjectSettings
    backup: BackupSettings
    devices: tuple[Device, ...]

    def enabled_devices(self) -> tuple[Device, ...]:
        return tuple(device for device in self.devices if device.enabled)

    def default_device(self) -> Device:
        devices = self.enabled_devices()
        if not devices:
            raise ConfigError("At least one enabled device is required")
        if self.project.default_device:
            for device in devices:
                if device.name == self.project.default_device:
                    return device
        return devices[0]

    def get_devices(self, names: list[str] | None = None) -> tuple[Device, ...]:
        devices = self.enabled_devices()
        if not names:
            return devices
        requested = set(names)
        found = {device.name for device in devices}
        missing = sorted(requested - found)
        if missing:
            raise ConfigError(f"Unknown or disabled device(s): {', '.join(missing)}")
        return tuple(device for device in devices if device.name in requested)

    def source_roots_for(self, device: Device) -> tuple[SourceRoot, ...]:
        return device.source_roots if device.source_roots is not None else self.backup.source_roots

    def display_path(self, value: str | Path) -> str:
        text = str(value)
        if not text:
            return ""
        normalized = text.replace("/", "\\")
        prefixes = sorted(
            (str(prefix).replace("/", "\\").rstrip("\\") for prefix in self.project.private_path_prefixes),
            key=len,
            reverse=True,
        )
        for prefix in prefixes:
            if not prefix:
                continue
            if normalized == prefix:
                return "..."
            if normalized.startswith(f"{prefix}\\"):
                return f"...\\{normalized[len(prefix) + 1:]}"
        return text

    def logs_path(self) -> Path:
        return self.project.logs_dir

    def state_path(self) -> Path:
        return self.project.state_dir


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    config_path = config_path.resolve()

    try:
        with config_path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config file is not valid JSON: {exc}") from exc

    root = config_path.parent.parent
    project = _parse_project(raw.get("project", {}), root)
    backup = _parse_backup(raw.get("backup", {}))
    devices = _parse_devices(raw.get("devices", []))

    names = [device.name for device in devices]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ConfigError(f"Duplicate device name(s): {', '.join(duplicates)}")
    if not devices:
        raise ConfigError("At least one device is required")

    return AppConfig(
        path=config_path,
        root=root,
        project=project,
        backup=backup,
        devices=devices,
    )


def _parse_project(raw: dict[str, Any], root: Path) -> ProjectSettings:
    private_path_prefixes = tuple(
        _resolve_path(root, item) for item in raw.get("private_path_prefixes", [])
    )
    return ProjectSettings(
        timezone=str(raw.get("timezone", "Asia/Shanghai")),
        destination_root=_resolve_path(root, _required(raw, "destination_root")),
        logs_dir=_resolve_path(root, raw.get("logs_dir", "logs")),
        state_dir=_resolve_path(root, raw.get("state_dir", "state")),
        lock_file=_resolve_path(root, raw.get("lock_file", "state/backup.lock")),
        robocopy_threads=_int_in_range(raw, "robocopy_threads", 8, 1, 128),
        default_device=str(raw.get("default_device") or "") or None,
        private_path_prefixes=private_path_prefixes,
    )


def _parse_backup(raw: dict[str, Any]) -> BackupSettings:
    source_roots = tuple(_parse_source_root(item) for item in raw.get("source_roots", []))
    if not source_roots:
        raise ConfigError("backup.source_roots must contain at least one source")

    return BackupSettings(
        dry_run_default=bool(raw.get("dry_run_default", True)),
        copy_empty_dirs=bool(raw.get("copy_empty_dirs", True)),
        retry_count=_int_in_range(raw, "retry_count", 2, 0, 1000),
        retry_wait_seconds=_int_in_range(raw, "retry_wait_seconds", 5, 0, 86400),
        smb_port=_int_in_range(raw, "smb_port", 445, 1, 65535),
        exclude_dirs=tuple(str(item) for item in raw.get("exclude_dirs", [])),
        exclude_files=tuple(str(item) for item in raw.get("exclude_files", [])),
        source_roots=source_roots,
    )


def _parse_devices(raw: list[dict[str, Any]]) -> tuple[Device, ...]:
    devices: list[Device] = []
    for item in raw:
        source_roots = item.get("source_roots")
        devices.append(
            Device(
                name=str(_required(item, "name")),
                ip=str(_required(item, "ip")),
                enabled=bool(item.get("enabled", True)),
                source_roots=(
                    tuple(_parse_source_root(source) for source in source_roots)
                    if source_roots is not None
                    else None
                ),
            )
        )
    return tuple(devices)


def _parse_source_root(raw: dict[str, Any]) -> SourceRoot:
    label = str(_required(raw, "label"))
    path_template = str(_required(raw, "path_template"))
    # Validate placeholders at load time so a bad template (unknown/positional
    # field) fails as a clean ConfigError here rather than an opaque
    # KeyError/IndexError deep inside build_jobs at backup/scan time.
    try:
        path_template.format(ip="0.0.0.0", name="_probe_")
    except (KeyError, IndexError, ValueError) as exc:
        raise ConfigError(
            f"Invalid path_template for source '{label}': {path_template!r} "
            f"(only {{ip}} and {{name}} placeholders are allowed) - {exc}"
        ) from exc
    return SourceRoot(
        label=label,
        path_template=path_template,
        enabled=bool(raw.get("enabled", True)),
    )


def _required(raw: dict[str, Any], key: str) -> Any:
    if key not in raw or raw[key] in (None, ""):
        raise ConfigError(f"Missing required config key: {key}")
    return raw[key]


def _int_in_range(
    raw: dict[str, Any], key: str, default: int, low: int, high: int
) -> int:
    value = raw.get(key, default)
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(
            f"Config key '{key}' must be an integer, got {value!r}"
        ) from exc
    if not low <= number <= high:
        raise ConfigError(
            f"Config key '{key}' must be between {low} and {high}, got {number}"
        )
    return number


def _resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (root / path).resolve()
