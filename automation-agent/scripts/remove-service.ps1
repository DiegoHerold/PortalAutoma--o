param([string]$ServiceName = "BiasonAutomationAgent")

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    exit 1
}

Write-Host "Stopping service..." -ForegroundColor Yellow
sc.exe stop $ServiceName 2>$null

Start-Sleep -Seconds 3

Write-Host "Removing service..." -ForegroundColor Yellow
sc.exe delete $ServiceName

if ($LASTEXITCODE -eq 0) {
    Write-Host "Service '$ServiceName' removed." -ForegroundColor Green
} else {
    Write-Host "Failed to remove service." -ForegroundColor Red
}
