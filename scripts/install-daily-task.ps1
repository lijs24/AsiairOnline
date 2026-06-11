param(
    [string]$At = "09:00",
    [string]$TaskName = "AsiairBridge Daily Backup"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackupScript = Join-Path $PSScriptRoot "backup-all.ps1"
$Time = [datetime]::ParseExact($At, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)

$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$BackupScript`" -Run"
$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ActionArgs `
    -WorkingDirectory $Root

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 18)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily ASIAIR incremental backup through asiairbridge." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' at $At."
