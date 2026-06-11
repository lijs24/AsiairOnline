param(
    [int]$Port = 8787,
    [string]$RuleName = "AsiairBridge Web Dashboard"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Existing = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($Existing) {
    Write-Host "Firewall rule '$RuleName' already exists."
    Write-Host "Review it with: Get-NetFirewallRule -DisplayName '$RuleName' | Get-NetFirewallPortFilter"
    exit 0
}

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -RemoteAddress "100.64.0.0/10" `
    -Profile Any | Out-Null

Write-Host "Allowed inbound TCP $Port from Tailscale address range 100.64.0.0/10."
