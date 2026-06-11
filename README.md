# AsiairOnline

ASIAIR remote operations and backup helper for Windows hosts that reach one or more ASIAIR boxes through Tailscale or a private LAN.

The project provides:

- Incremental, dry-run-by-default backup from ASIAIR SMB shares to a local material library.
- A web dashboard for live device monitoring, camera preview/control, and local material browsing.
- A local SQLite index for cached material metadata and generated preview images.
- Per-device control leases so multiple tailnet users can watch the dashboard while write actions stay gated to a single controller.

## Quick Start

Create a local config from the public template:

```powershell
Copy-Item .\config\devices.example.json .\config\devices.json
notepad .\config\devices.json
```

Fill in your real ASIAIR names, IPs, SMB source shares, backup destination, and optional private path prefixes. `config/devices.json` is intentionally ignored by git.

Run local checks:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\doctor.ps1
```

Preview the backup plan without copying data (dry run is the default):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-all.ps1
```

Run the approved incremental backup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-all.ps1 -Run
```

Start the local-only web dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-web.ps1
```

Open `http://127.0.0.1:8787/` and you land on the live monitor.

## Web Dashboard

The dashboard root is the live monitor; the other pages are reached from there:

| Path | Page |
| --- | --- |
| `/` or `/monitor-minterm` | Live device monitor (MINTERM ops console) — the landing page |
| `/camera` | Current-image preview, camera status, exposure and camera controls (requires the control lease) |
| `/materials` | Local material library browser, backed by the backup destination and cached previews |

> The legacy backup-console landing page and the old `/monitor` page have been removed; the live monitor is now the default landing page. The `/api/*` JSON endpoints (status, devices, rpc-monitor, materials, camera, …) are unchanged.

### Read-only vs. writable

Access to write actions (start a backup, control the camera) is gated in layers:

- The server binds `127.0.0.1` by default (local only).
- `-ReadOnly` runs a monitoring-only server: viewers can watch but can never start backups or drive the camera.
- Without `-ReadOnly`, non-loopback (tailnet) clients are still restricted to read-only **unless** the server was started with `-AllowRemoteActions`.
- Camera control additionally requires holding the per-device **control lease** — claim "controller" in the UI before exposure/shutter commands are accepted.

### Tailnet access

Find the server address with `tailscale ip -4`, then either:

- **Monitoring for the whole tailnet:** `scripts\start-tailnet-web.ps1` fronts a read-only backend with Tailscale Serve.
- **Control from another tailnet device:** `scripts\start-web.ps1 -HostName 0.0.0.0 -AllowRemoteActions` (writable). Run only one writable instance per device — see [Deployment](#deployment-one-writable-controller-per-device).

## Configuration

All environment-specific values live in `config/devices.json`:

- ASIAIR device names and IP addresses.
- Enabled SMB shares such as `EMMC Images`, `TF Images`, or `Udisk Images`.
- Local backup destination.
- Default device for the dashboard.
- Private path prefixes that should be folded in the UI display.
- Backup retry, exclusion, and robocopy settings.

Keep credentials outside this repository. Use Windows Credential Manager, `net use`, Tailscale authentication, or another external secret store.

## Reliability

- Backups default to dry-run; a real copy requires `-Run` / `--no-dry-run`.
- A stale lock left by a crashed or killed backup is reclaimed automatically once its PID is confirmed dead, so scheduled backups self-heal. `--force-lock` refuses to clear a lock whose owner is still alive, preventing two concurrent runs against the same destination.
- Run-state and cache files are written atomically (temp file + `os.replace`); a crash mid-write cannot leave a truncated file.
- robocopy output is decoded with the Windows OEM code page, so non-ASCII (e.g. Chinese) source/destination paths stay readable in logs and the dashboard.
- Device RPC reads are bounded by the per-call timeout budget and a response-size cap, so a slow or misbehaving box cannot stall the monitor or grow memory without bound.
- Configuration is range-validated at load time and reports a clear error instead of an opaque traceback.

## Deployment: one writable controller per device

Each running web server independently polls every configured device and can issue control commands. The ASIAIR is a single-controller device, and the control lease only coordinates instances that **share the same `state/` directory** (i.e. the same host).

- Run exactly **one writable controller** per ASIAIR device; run any additional instances with `-ReadOnly` as monitors.
- Do **not** run writable instances on different machines pointing at the same device — they cannot coordinate and will send conflicting commands, which can disrupt a live imaging session.
- For many viewers, expose a single backend through Tailscale Serve rather than starting multiple writable servers. More instances also multiply the RPC polling load on the device.

## Safety

- Backups are incremental and never mirror-delete. The project does not use destructive flags such as `robocopy /MIR` or `/PURGE`, and does not delete remote or local data.
- The web server binds `127.0.0.1` by default. Bind to `0.0.0.0` (and pass `-AllowRemoteActions`) only when you intentionally want writable tailnet access.
- Keep all ASIAIR, SMB, SSH, and Tailscale credentials out of the repository.

## Project Layout

- `config/devices.example.json`: public example configuration.
- `src/asiairbridge/`: Python CLI, backup logic, JSON-RPC client and monitor, web server, camera operations, and material library.
- `scripts/`: Windows PowerShell entry points (`doctor`, `backup-all`, `start-web`, `start-tailnet-web`, scheduled-task installers).
- `docs/asiair-monitor-minterm-live.html`: live monitor frontend (dashboard landing page).
- `docs/asiair-image-preview.html`: camera frontend.
- `docs/asiair-materials.html`: material library frontend.
- `logs/`: per-run logs, git-ignored.
- `state/`: runtime state, locks, caches, SQLite databases, and generated previews, git-ignored.
