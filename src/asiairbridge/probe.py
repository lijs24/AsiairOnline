from __future__ import annotations

import locale
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    detail: str


def robocopy_available() -> ProbeResult:
    path = shutil.which("robocopy")
    if path:
        return ProbeResult(True, path)
    return ProbeResult(False, "robocopy was not found on PATH")


def ping_host(host: str, timeout_ms: int = 1000) -> ProbeResult:
    cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except OSError as exc:
        return ProbeResult(False, str(exc))
    detail = _first_meaningful_line(proc.stdout) or _first_meaningful_line(proc.stderr)
    return ProbeResult(proc.returncode == 0, detail or f"exit {proc.returncode}")


def tcp_open(host: str, port: int, timeout_seconds: float = 2.0) -> ProbeResult:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return ProbeResult(True, f"tcp/{port} open")
    except OSError as exc:
        return ProbeResult(False, f"tcp/{port} closed or unreachable: {exc}")


def path_exists(path: Path) -> ProbeResult:
    try:
        if path.exists():
            return ProbeResult(True, "exists")
        return ProbeResult(False, "not found")
    except OSError as exc:
        return ProbeResult(False, str(exc))


def net_view(host: str) -> ProbeResult:
    cmd = ["net", "view", f"\\\\{host}"]
    encoding = locale.getpreferredencoding(False)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace",
        )
    except OSError as exc:
        return ProbeResult(False, str(exc))
    output = (proc.stdout + "\n" + proc.stderr).strip()
    return ProbeResult(proc.returncode == 0, output or f"exit {proc.returncode}")


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""
