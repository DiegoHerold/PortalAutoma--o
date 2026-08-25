# =====================================================================
# Biason - Automation Agent: build + test real no Windows
# Roda no PowerShell, na sua maquina, usando o SDK/NuGet que voce ja tem
# instalado (o sandbox da nuvem nao tem acesso ao nuget.org, por isso
# isso precisa rodar aqui e nao la).
#
# Como usar:
#   1) Abra o PowerShell nesta pasta (a raiz do PortalAutomação)
#   2) Rode:  powershell -ExecutionPolicy Bypass -File .\test-agent.ps1
#   3) Quando terminar, me mande o arquivo
#      automation-agent-build-test-log.txt que vai aparecer nesta mesma pasta
#      (ou cole o resultado no chat).
# =====================================================================

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$logFile = Join-Path $root "automation-agent-build-test-log.txt"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

function Log($msg) {
    Write-Host $msg
    Add-Content -Path $logFile -Value $msg
}

function Section($title) {
    $line = "`n========== $title =========="
    Log $line
}

Section "1) Ambiente"
Log "Data/hora: $(Get-Date)"
Log "Pasta raiz: $root"
try { Log ("dotnet: " + (dotnet --version)) } catch { Log "dotnet: NAO ENCONTRADO no PATH" }
try { Log ("docker: " + (docker --version)) } catch { Log "docker: NAO ENCONTRADO no PATH" }

Section "2) Containers Docker do Portal (docker compose ps)"
Push-Location $root
try {
    $composeOut = docker compose ps 2>&1 | Out-String
    Log $composeOut
} catch {
    Log "Falha ao rodar 'docker compose ps': $_"
}
Pop-Location

Section "3) Health check do backend (http://localhost:8000/health)"
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    Log ("Health OK: " + ($health | ConvertTo-Json -Compress))
} catch {
    Log "Health check FALHOU (backend pode nao estar rodando na porta 8000): $_"
}

$agentDir = Join-Path $root "automation-agent"
if (-not (Test-Path $agentDir)) {
    Log "`nERRO: nao encontrei a pasta automation-agent em $root - ajuste o caminho no topo do script."
    exit 1
}
Set-Location $agentDir

Section "4) dotnet restore AutomationAgent.sln"
$restoreOut = dotnet restore AutomationAgent.sln 2>&1 | Out-String
Log $restoreOut

Section "5) dotnet build AutomationAgent.sln -c Release"
$buildOut = dotnet build AutomationAgent.sln -c Release --no-restore 2>&1 | Out-String
Log $buildOut
if ($LASTEXITCODE -eq 0) { Log "`n>>> BUILD OK (AutomationAgent.sln)" } else { Log "`n>>> BUILD FALHOU (AutomationAgent.sln) - exit code $LASTEXITCODE" }

Section "6) dotnet test tests\Agent.UnitTests"
$unitOut = dotnet test tests\Agent.UnitTests\Agent.UnitTests.csproj -c Release --no-restore 2>&1 | Out-String
Log $unitOut

Section "7) dotnet test tests\Agent.IntegrationTests"
$intOut = dotnet test tests\Agent.IntegrationTests\Agent.IntegrationTests.csproj -c Release --no-restore 2>&1 | Out-String
Log $intOut

Section "8) Certification.sln (harness de certificacao end-to-end)"
$certRestoreOut = dotnet restore Certification.sln 2>&1 | Out-String
Log $certRestoreOut
$certBuildOut = dotnet build Certification.sln -c Release --no-restore 2>&1 | Out-String
Log $certBuildOut
$certTestOut = dotnet test tests\Certification.Tests\Certification.Tests.csproj -c Release --no-restore 2>&1 | Out-String
Log $certTestOut

Section "RESUMO"
Log "Log completo salvo em: $logFile"
Log "Me mande esse arquivo (ou o texto do terminal) para eu analisar o resultado real."

Write-Host "`n`nPronto! Log completo em: $logFile" -ForegroundColor Green
