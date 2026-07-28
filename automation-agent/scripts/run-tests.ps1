$ErrorActionPreference = "Stop"
$SolutionDir = Split-Path $PSScriptRoot

Write-Host "Running all tests..." -ForegroundColor Cyan
dotnet test "$SolutionDir\AutomationAgent.sln" --verbosity normal

if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "All tests passed." -ForegroundColor Green
