# Publish self-contained executable for Windows x64
param(
    [string]$Configuration = "Release",
    [string]$OutputDir = "..\publish"
)

$ErrorActionPreference = "Stop"
$SolutionDir = Split-Path $PSScriptRoot

Write-Host "Publishing Biason Automation Agent..." -ForegroundColor Cyan

dotnet publish `
    "$SolutionDir\src\Agent.Service\Agent.Service.csproj" `
    --configuration $Configuration `
    --runtime win-x64 `
    --self-contained true `
    --output "$SolutionDir\$OutputDir" `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true

if ($LASTEXITCODE -ne 0) {
    Write-Host "Publish FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "Published to: $SolutionDir\$OutputDir" -ForegroundColor Green
Write-Host "Executable: AgentService.exe" -ForegroundColor Green
