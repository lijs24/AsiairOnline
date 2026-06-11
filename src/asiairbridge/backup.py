from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import AppConfig, Device, SourceRoot
from .probe import tcp_open


@dataclass(frozen=True)
class BackupJob:
    device: Device
    source: SourceRoot
    source_path: Path
    destination_path: Path
    log_path: Path


@dataclass(frozen=True)
class BackupResult:
    job: BackupJob
    ok: bool
    status: str
    exit_code: int | None
    detail: str
    started_at: str
    finished_at: str


def build_jobs(
    config: AppConfig,
    run_id: str,
    device_names: list[str] | None = None,
    source_labels: list[str] | None = None,
) -> list[BackupJob]:
    selected_labels = set(source_labels or [])
    jobs: list[BackupJob] = []
    day_dir = config.logs_path() / datetime.now().strftime("%Y-%m-%d")

    for device in config.get_devices(device_names):
        for source in config.source_roots_for(device):
            if not source.enabled:
                continue
            if selected_labels and source.label not in selected_labels:
                continue
            source_path = source.render(device)
            destination_path = config.project.destination_root / device.name / source.safe_label
            log_name = f"{run_id}_{device.name}_{source.safe_label}.log"
            jobs.append(
                BackupJob(
                    device=device,
                    source=source,
                    source_path=source_path,
                    destination_path=destination_path,
                    log_path=day_dir / log_name,
                )
            )

    return jobs


def run_job(config: AppConfig, job: BackupJob, dry_run: bool) -> BackupResult:
    started_at = datetime.now().isoformat(timespec="seconds")
    port = config.backup.smb_port
    tcp = tcp_open(job.device.ip, port)
    if not tcp.ok:
        finished_at = datetime.now().isoformat(timespec="seconds")
        return BackupResult(
            job=job,
            ok=False,
            status="skipped",
            exit_code=None,
            detail=tcp.detail,
            started_at=started_at,
            finished_at=finished_at,
        )

    robocopy = shutil.which("robocopy")
    if not robocopy:
        finished_at = datetime.now().isoformat(timespec="seconds")
        return BackupResult(
            job=job,
            ok=False,
            status="failed",
            exit_code=None,
            detail="robocopy not found",
            started_at=started_at,
            finished_at=finished_at,
        )

    job.log_path.parent.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        job.destination_path.mkdir(parents=True, exist_ok=True)

    cmd = _robocopy_command(config, robocopy, job, dry_run)
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    finished_at = datetime.now().isoformat(timespec="seconds")
    ok = proc.returncode < 8
    detail = _summarize_process(proc)

    return BackupResult(
        job=job,
        ok=ok,
        status="ok" if ok else "failed",
        exit_code=proc.returncode,
        detail=detail,
        started_at=started_at,
        finished_at=finished_at,
    )


def result_to_dict(result: BackupResult) -> dict[str, object]:
    job = result.job
    return {
        "device": job.device.name,
        "ip": job.device.ip,
        "source_label": job.source.label,
        "source_path": str(job.source_path),
        "destination_path": str(job.destination_path),
        "log_path": str(job.log_path),
        "ok": result.ok,
        "status": result.status,
        "exit_code": result.exit_code,
        "detail": result.detail,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
    }


def _robocopy_command(
    config: AppConfig,
    robocopy: str,
    job: BackupJob,
    dry_run: bool,
) -> list[str]:
    command = [
        robocopy,
        str(job.source_path),
        str(job.destination_path),
        "/E" if config.backup.copy_empty_dirs else "/S",
        "/Z",
        "/FFT",
        f"/R:{config.backup.retry_count}",
        f"/W:{config.backup.retry_wait_seconds}",
        "/XJ",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/NP",
        "/TEE",
        f"/LOG+:{job.log_path}",
        f"/MT:{config.project.robocopy_threads}",
    ]
    if dry_run:
        command.append("/L")
    if config.backup.exclude_dirs:
        command.append("/XD")
        command.extend(config.backup.exclude_dirs)
    if config.backup.exclude_files:
        command.append("/XF")
        command.extend(config.backup.exclude_files)
    return command


def _summarize_process(proc: subprocess.CompletedProcess[str]) -> str:
    lines = []
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    if not lines:
        return f"robocopy exit {proc.returncode}"
    return lines[-1][:500]
