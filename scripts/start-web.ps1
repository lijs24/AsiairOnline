param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8787,
    [string]$Config,
    [string]$Python = "python",
    [switch]$AllowRemoteActions,
    [switch]$ReadOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Config) {
    $Config = Join-Path $Root "config\devices.json"
}

$env:PYTHONPATH = Join-Path $Root "src"
$env:PYTHONDONTWRITEBYTECODE = "1"

$Src = Join-Path $Root "src"
$ActionArg = if ($AllowRemoteActions) { "['--allow-remote-actions']" } else { "[]" }
$ReadOnlyArg = if ($ReadOnly) { "['--read-only']" } else { "[]" }
$Code = @"
import sys
sys.path.insert(0, r'''$Src''')
from asiairbridge.cli import main
args = ['--config', r'''$Config''', 'web', '--host', r'''$HostName''', '--port', '$Port'] + $ActionArg + $ReadOnlyArg
raise SystemExit(main(args))
"@

& $Python -B -c $Code
exit $LASTEXITCODE
