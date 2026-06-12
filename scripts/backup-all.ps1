param(
    [switch]$Run,
    [string]$Config,
    [string]$Python = "python",
    [string[]]$Device,
    [string[]]$SourceLabel,
    [switch]$ForceLock
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Config) {
    $Config = Join-Path $Root "config\devices.json"
}

$env:PYTHONPATH = Join-Path $Root "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$CmdArgs = @("-m", "asiairbridge", "--config", $Config, "backup")

if ($Run) {
    $CmdArgs += "--no-dry-run"
} else {
    $CmdArgs += "--dry-run"
}

foreach ($Name in $Device) {
    $CmdArgs += @("--device", $Name)
}

foreach ($Label in $SourceLabel) {
    $CmdArgs += @("--source-label", $Label)
}

if ($ForceLock) {
    $CmdArgs += "--force-lock"
}

& $Python @CmdArgs
$BackupExit = $LASTEXITCODE

if ($Run -and $BackupExit -eq 0) {
    # Refresh the material-library index so the web pages see the new files.
    try {
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8787/api/materials/scan" `
            -ContentType "application/json" -Body (ConvertTo-Json @{ force = $true }) -TimeoutSec 15 | Out-Null
        Write-Host "Material index scan triggered."
    } catch {
        Write-Warning "Could not trigger the material index scan: $_"
    }
}
exit $BackupExit
