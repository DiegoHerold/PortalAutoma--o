# =====================================================================
# Biason - Automation Agent: prova real de execucao em TODOS os runtimes
#
# Este script builda o Agent, publica um ExecutionHost.exe FRESCO (item
# novo desta rodada - veja secao 6), reinicia o Agent.Service, provisiona
# os runtimes que faltam (Playwright/Chromium, pyautogui - secao 9) e
# dispara, contra o SEU Agent.Service ja online no Portal, uma execucao
# real de cada tipo de entrypoint que a Biason realmente precisa:
#   - python_function   (app/processo em 2o plano - ja provado antes)
#   - powershell_script (visivel ou invisivel, conforme execution.mode)
#   - executable        (idem)
#   - browser_playwright (navegador real via Playwright - NOVO)
# e imprime um resumo PASS/FAIL genuino por tipo. No final, roda tambem
# a curadoria do catalogo de Runtimes do Portal (secao 11).
#
# Pre-requisitos:
#   - O Agent.Service da certificacao (ou de producao) precisa estar
#     rodando e conectado/online no Portal.
#   - Docker do Portal rodando (docker compose ps).
#   - Internet nesta maquina (secao 9 baixa Playwright/Chromium na
#     primeira vez - pode demorar alguns minutos so na primeira rodada).
#
# Como usar:
#   powershell -ExecutionPolicy Bypass -File .\test-agent-all-runtimes.ps1
# =====================================================================

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$logFile = Join-Path $root "all-runtimes-log.txt"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

function Log($msg) {
    Write-Host $msg
    Add-Content -Path $logFile -Value $msg
}

function Section($title) {
    Log "`n========== $title =========="
}

# Roda um comando externo transmitindo a saida em tempo real (evita o
# problema do script anterior, que usava "| Out-String" e prendia toda a
# saida ate o processo terminar - parecia "travado" mesmo funcionando).
function RunStreamed($exe, $argList) {
    & $exe @argList 2>&1 | ForEach-Object {
        Write-Host $_
        Add-Content -Path $logFile -Value $_
    }
    return $LASTEXITCODE
}

Section "0) Ambiente"
Log "Data/hora: $(Get-Date)"
Log "Pasta raiz: $root"
try { Log ("dotnet: " + (dotnet --version)) } catch { Log "dotnet: NAO ENCONTRADO no PATH" }
try { Log ("docker: " + (docker --version)) } catch { Log "docker: NAO ENCONTRADO no PATH" }

$pwshOnPath = Get-Command pwsh.exe -ErrorAction SilentlyContinue
if ($pwshOnPath) {
    Log "PowerShell 7 (pwsh.exe): encontrado em $($pwshOnPath.Source)"
} else {
    Log "PowerShell 7 (pwsh.exe): NAO encontrado no PATH desta maquina."
    Log "  -> O Agent cai para o Windows PowerShell 5.1 (powershell.exe) automaticamente nesse caso."
}

$agentDir = Join-Path $root "automation-agent"
if (-not (Test-Path $agentDir)) {
    Log "`nERRO: nao encontrei a pasta automation-agent em $root - ajuste o caminho no topo do script."
    exit 1
}

Section "1) docker compose ps"
Push-Location $root
RunStreamed "docker" @("compose", "ps") | Out-Null
Pop-Location

Section "2) Health check do backend"
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10
    Log ("Health OK: " + ($health | ConvertTo-Json -Compress))
} catch {
    Log "Health check FALHOU (backend pode nao estar rodando na porta 8000): $_"
}

Set-Location $agentDir

Section "3) dotnet restore + build AutomationAgent.sln -c Release (com as correcoes desta sessao)"
$exitRestore = RunStreamed "dotnet" @("restore", "AutomationAgent.sln")
$exitBuild = RunStreamed "dotnet" @("build", "AutomationAgent.sln", "-c", "Release", "--no-restore")
if ($exitBuild -eq 0) { Log "`n>>> BUILD OK" } else { Log "`n>>> BUILD FALHOU - exit code $exitBuild" }

Section "4) dotnet test tests\Agent.UnitTests (inclui os testes novos das correcoes)"
$exitUnit = RunStreamed "dotnet" @("test", "tests\Agent.UnitTests\Agent.UnitTests.csproj", "-c", "Release", "--no-restore")
if ($exitUnit -eq 0) { Log "`n>>> TESTES UNITARIOS OK" } else { Log "`n>>> TESTES UNITARIOS FALHARAM - exit code $exitUnit" }

Section "5) Recompilando o harness de certificacao (Certification.sln)"
$exitCertRestore = RunStreamed "dotnet" @("restore", "Certification.sln")
$exitCertBuild = RunStreamed "dotnet" @("build", "Certification.sln", "-c", "Release", "--no-restore")
if ($exitCertBuild -eq 0) { Log "`n>>> BUILD do harness OK" } else { Log "`n>>> BUILD do harness FALHOU - exit code $exitCertBuild" }

Section "6) Publicando um ExecutionHost.exe FRESCO (ACHADO NOVO desta rodada)"
Log "ACHADO: 'dotnet build AutomationAgent.sln' (secao 3) as vezes NAO deixa um"
Log "ExecutionHost.exe fresco no caminho que o Agent.Service realmente procura"
Log "(ProcessTreeManager.ResolveExecutionHostPath - ele pega o .exe de data de"
Log "modificacao mais recente entre varios caminhos candidatos, mas so entre os"
Log "que EXISTEM no disco). Se nenhum candidato for atualizado pelo build da"
Log "solution, o Agent continua achando um ExecutionHost.exe de dias atras -"
Log "foi exatamente isso que causou o 'Execution failed' generico visto na ultima"
Log "rodada (o log real do ExecutionHost, em"
Log "certification-runs\agent-data\executions\<id>\<attempt>\logs\execution-host-.log,"
Log "mostrava 'Missing required path: RuntimePath' vindo de um Program.cs que ja"
Log "tinha sido reescrito ha varios commits - prova de binario desatualizado)."
Log "Este passo publica (self-contained, single-file, win-x64) o ExecutionHost"
Log "direto no caminho que o Agent.Service verifica primeiro depois do mais novo -"
Log "bin\Release\net8.0\win-x64\ExecutionHost.exe - garantindo que a versao"
Log "corrigida (ExecutionHostPathValidator, que ja sabe que powershell_script e"
Log "executable NAO precisam de RuntimePath) seja sempre a mais recente."
$hostProj = Join-Path $agentDir "src\Agent.ExecutionHost\Agent.ExecutionHost.csproj"
$hostOutDir = Join-Path $agentDir "src\Agent.ExecutionHost\bin\Release\net8.0\win-x64"
$exitHostPublish = RunStreamed "dotnet" @("publish", $hostProj, "-c", "Release", "-r", "win-x64", "--self-contained", "true", "-p:PublishSingleFile=true", "-o", $hostOutDir)
$hostExePath = Join-Path $hostOutDir "ExecutionHost.exe"
if ((Test-Path $hostExePath) -and $exitHostPublish -eq 0) {
    Log "`n>>> ExecutionHost.exe publicado em $hostExePath ($((Get-Item $hostExePath).LastWriteTime))"
} else {
    Log "`n>>> FALHA ao publicar ExecutionHost.exe (exit code $exitHostPublish) - powershell_script/executable"
    Log "    provavelmente vao continuar falhando com o binario antigo."
}

Section "7) Reiniciando o Agent.Service (ESSENCIAL - sem isso ele continua rodando o binario ANTIGO)"
Log "O Agent.Service que aparece 'Online' e um processo de longa duracao - recompilar"
Log "a solution (secao 3) ou publicar o ExecutionHost (secao 6) nao afeta um processo"
Log "que ja esta de pe. Este passo para o Agent.Service antigo e sobe um novo, ja com"
Log "o binario corrigido e o ExecutionHost fresco, antes de disparar as execucoes reais."
$certDll = Join-Path $agentDir "tools\Certification.Cli\bin\Release\net8.0\certification.dll"
if (-not (Test-Path $certDll)) {
    Log "ERRO: nao encontrei $certDll - o build do harness (secao 5) falhou, entao nao da pra"
    Log "reiniciar o Agent.Service automaticamente. As execucoes abaixo provavelmente vao"
    Log "continuar usando o binario antigo."
} else {
    Push-Location $root
    Log "`n--- certification stop (para o Agent.Service antigo, se estiver rodando) ---"
    RunStreamed "dotnet" @($certDll, "stop") | Out-Null
    Start-Sleep -Seconds 2
    Log "`n--- certification start (sobe o Agent.Service com o binario RECEM compilado) ---"
    $exitCertStart = RunStreamed "dotnet" @($certDll, "start")
    Pop-Location
    if ($exitCertStart -eq 0) { Log "`n>>> Agent.Service reiniciado e ONLINE com o binario novo" }
    else { Log "`n>>> FALHA ao reiniciar o Agent.Service - exit code $exitCertStart (veja o log acima). As execucoes abaixo podem ficar pendentes de novo." }
}

Section "8) Compilando ExampleTool.exe de verdade (prova o entrypoint 'executable')"
$toolProj = Join-Path $agentDir "tools\ExampleTool\ExampleTool.csproj"
$exeOutDir = Join-Path $agentDir "certification\demo_executable\automation"
if (-not (Test-Path $toolProj)) {
    Log "ERRO: nao encontrei $toolProj"
} else {
    New-Item -ItemType Directory -Force -Path $exeOutDir | Out-Null
    $exitPublish = RunStreamed "dotnet" @("publish", $toolProj, "-c", "Release", "-r", "win-x64", "--self-contained", "true", "-p:PublishSingleFile=true", "-o", $exeOutDir)
    $exePath = Join-Path $exeOutDir "ExampleTool.exe"
    if ((Test-Path $exePath) -and $exitPublish -eq 0) {
        Log "`n>>> ExampleTool.exe publicado em $exePath"
    } else {
        Log "`n>>> FALHA ao publicar ExampleTool.exe (exit code $exitPublish)"
    }
}

Section "9) Provisionando runtimes que faltam (Playwright/Chromium, pyautogui)"
$provisionScript = Join-Path $root "provision-runtimes.ps1"
if (-not (Test-Path $provisionScript)) {
    Log "AVISO: nao encontrei provision-runtimes.ps1 em $root - o runtime browser_playwright"
    Log "provavelmente vai falhar com 'Runtime not found: python-browser:3.13-playwright'."
} else {
    Log "Rodando provision-runtimes.ps1 (idempotente - so baixa o que ainda nao existe;"
    Log "pode demorar alguns minutos na primeira vez, baixando o Chromium do Playwright)..."
    & $provisionScript 2>&1 | ForEach-Object {
        Write-Host $_
        Add-Content -Path $logFile -Value $_
    }
    if ($LASTEXITCODE -eq 0) { Log "`n>>> Runtimes provisionados (python-browser-3.13-playwright, python-desktop-3.13)" }
    else { Log "`n>>> Provisionamento teve falha(s) - veja provision-runtimes-log.txt para detalhes." }
}

Section "10) Verificando pacotes de demonstracao"
foreach ($pkg in @("demo_fiscal", "demo_powershell", "demo_executable", "demo_browser")) {
    $pkgPath = Join-Path $agentDir "certification\$pkg\automation.json"
    if (Test-Path $pkgPath) { Log "OK: $pkg (automation.json encontrado)" }
    else { Log "AVISO: $pkg NAO encontrado em $pkgPath - a rodada abaixo vai pular esse runtime." }
}

Section "11) Rodando UMA EXECUCAO REAL por tipo de entrypoint contra o Agent online"
Push-Location $root
$exitDemo = RunStreamed "docker" @("compose", "exec", "-T", "backend", "python", "-m", "tools.certification.demo_all_runtimes")
Pop-Location
if ($exitDemo -eq 0) { Log "`n>>> TODOS os runtimes passaram (PASS)" } else { Log "`n>>> Pelo menos um runtime FALHOU - exit code $exitDemo (veja o resumo acima)" }

Section "12) Curadoria do catalogo de Runtimes do Portal (mantem so os que a Biason usa)"
Push-Location $root
$exitCurate = RunStreamed "docker" @("compose", "exec", "-T", "backend", "python", "-m", "tools.certification.curate_runtime_catalog")
Pop-Location
if ($exitCurate -eq 0) { Log "`n>>> Curadoria concluida sem falhas" } else { Log "`n>>> Curadoria teve falha(s) - exit code $exitCurate (veja o resumo acima)" }

Section "RESUMO"
Log "Log completo salvo em: $logFile"
Log "Me manda esse arquivo (ou o texto do terminal) que eu leio o resultado real."

Write-Host "`n`nPronto! Log completo em: $logFile" -ForegroundColor Green
