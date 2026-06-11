param(
    [string]$TaskName = "AsiairBridge Web Dashboard",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8787,
    [switch]$AllowRemoteActions
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$WebScript = Join-Path $PSScriptRoot "start-web.ps1"

$RemoteActionArg = if ($AllowRemoteActions) { " -AllowRemoteActions" } else { "" }
$ActionArgs = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WebScript`" -HostName $HostName -Port $Port$RemoteActionArg"
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
    -Description "Local asiairbridge web dashboard." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' at logon."
