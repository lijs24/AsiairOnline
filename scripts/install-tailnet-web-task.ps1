param(
    [string]$TaskName = "AsiairBridge Tailnet Dashboard",
    [int]$PublicPort = 8787,
    [int]$BackendPort = 8788
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Script = Join-Path $PSScriptRoot "start-tailnet-web.ps1"

$ActionArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`" -PublicPort $PublicPort -BackendPort $BackendPort"
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ActionArgs `
    -WorkingDirectory $Root

$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Days 30)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Read-only asiairbridge dashboard exposed through Tailscale Serve." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' at logon."
