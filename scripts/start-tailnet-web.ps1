param(
    [int]$PublicPort = 8787,
    [int]$BackendPort = 8788
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$StartWeb = Join-Path $PSScriptRoot "start-web.ps1"

$Existing = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
if (-not $Existing) {
    Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $StartWeb,
            "-HostName",
            "127.0.0.1",
            "-Port",
            "$BackendPort",
            "-ReadOnly"
        ) `
        -WorkingDirectory $Root `
        -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
}

& (Join-Path $PSScriptRoot "enable-tailscale-serve.ps1") `
    -PublicPort $PublicPort `
    -BackendPort $BackendPort
