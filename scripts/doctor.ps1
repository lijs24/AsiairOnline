param(
    [string]$Config,
    [string]$Python = "python",
    [string[]]$Device
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Config) {
    $Config = Join-Path $Root "config\devices.json"
}

$env:PYTHONPATH = Join-Path $Root "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$CmdArgs = @("-m", "asiairbridge", "--config", $Config, "doctor")

foreach ($Name in $Device) {
    $CmdArgs += @("--device", $Name)
}

& $Python @CmdArgs
exit $LASTEXITCODE
