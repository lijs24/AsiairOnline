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
exit $LASTEXITCODE
