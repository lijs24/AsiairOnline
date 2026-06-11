from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class RunLock:
    def __init__(
        self,
        path: Path,
        force: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.force = force
        self.metadata = metadata or {}
        self._fd: int | None = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.force and self.path.exists():
            self.path.unlink()
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError(f"Another backup run appears active: {self.path}") from exc

        payload = {
            "pid": os.getpid(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        payload.update(self.metadata)
        os.write(self._fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def write_run_state(state_dir: Path, run_id: str, payload: dict[str, Any]) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = state_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_path = runs_dir / f"{run_id}.json"
    latest_path = state_dir / "latest.json"

    _write_json(run_path, payload)
    _write_json(latest_path, payload)
    return run_path


def read_latest_state(state_dir: Path) -> dict[str, Any] | None:
    latest_path = state_dir / "latest.json"
    if not latest_path.exists():
        return None
    with latest_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
