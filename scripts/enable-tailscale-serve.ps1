param(
    [int]$PublicPort = 8787,
    [int]$BackendPort = 8788,
    [string]$BackendHost = "127.0.0.1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Target = "${BackendHost}:${BackendPort}"

$PreviousPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
tailscale serve --tcp=$PublicPort off 2>$null | Out-Null
tailscale serve --http=$PublicPort off 2>$null | Out-Null
$ErrorActionPreference = $PreviousPreference
tailscale serve --bg --tcp=$PublicPort $Target
tailscale serve status
