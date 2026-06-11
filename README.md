# AsiairOnline

ASIAIR remote operations and backup helper for Windows hosts that reach one or more ASIAIR boxes through Tailscale or a private LAN.

The project provides:

- Incremental backup from ASIAIR SMB shares to a local material library.
- A web dashboard for device monitoring, camera preview, camera controls, and local material browsing.
- A local SQLite index for cached material metadata and generated preview images.
- Per-device control leases so multiple tailnet users can watch the dashboard while write actions stay gated.

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

Preview the backup plan without copying data:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-all.ps1
```

Run the approved incremental backup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-all.ps1 -Run
```

Start the local-only web service:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-web.ps1
```

Expose the dashboard to other devices in the same tailnet:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-web.ps1 -HostName 0.0.0.0
```

Then open `http://<server-tailnet-ip>:8787/` from another Tailscale device. Use `tailscale ip -4` on the server to find the address.

## Web Pages

- `/monitor-minterm`: high-density live monitor.
- `/camera`: current image preview, camera status, exposure controls, and camera controls protected by the main-control lease.
- `/materials`: local material library browser backed by the configured backup destination and cached preview images.

## Configuration

All environment-specific values live in `config/devices.json`:

- ASIAIR device names and IP addresses.
- Enabled SMB shares such as `EMMC Images`, `TF Images`, or `Udisk Images`.
- Local backup destination.
- Default device for the dashboard.
- Private path prefixes that should be folded in the UI display.
- Backup retry, exclusion, and robocopy settings.

Keep credentials outside this repository. Use Windows Credential Manager, `net use`, Tailscale authentication, or another external secret store.

## Safety

Backup commands are incremental and do not mirror-delete. The project does not use destructive flags such as `robocopy /MIR` or `/PURGE`.

By default, the web server binds to `127.0.0.1`. Bind to `0.0.0.0` only when you intentionally want tailnet access.

## Project Layout

- `config/devices.example.json`: public example configuration.
- `src/asiairbridge/`: Python CLI, backup logic, JSON-RPC monitor, web server, camera operations, and material library.
- `scripts/`: Windows PowerShell entry points.
- `docs/asiair-monitor-minterm-live.html`: live monitor frontend.
- `docs/asiair-image-preview.html`: camera frontend.
- `docs/asiair-materials.html`: material library frontend.
- `logs/`: per-run logs, git-ignored.
- `state/`: runtime state, locks, caches, SQLite databases, and generated previews, git-ignored.
