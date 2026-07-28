# Install Agent as Windows Service (requires elevation)
param(
    [string]$ExePath = "..\publish\AgentService.exe",
    [string]$ServiceName = "BiasonAutomationAgent",
    [string]$DisplayName = "Biason Automation Agent",
    [string]$Description = "Automation Agent for Biason Assessoria Empresarial"
)

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
    Write-Host "ERROR: Run this script as Administrator." -ForegroundColor Red
    exit 1
}

$FullPath = Resolve-Path $ExePath -ErrorAction Stop

Write-Host "Installing service '$ServiceName'..." -ForegroundColor Cyan

sc.exe create $ServiceName `
    binPath= "`"$FullPath`"" `
    start= delayed-auto `
    DisplayName= $DisplayName

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to create service" -ForegroundColor Red
    exit 1
}

sc.exe description $ServiceName $Description
sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/120000/restart/300000

Write-Host "Service '$ServiceName' installed." -ForegroundColor Green
Write-Host "Start with: sc.exe start $ServiceName" -ForegroundColor Yellow
