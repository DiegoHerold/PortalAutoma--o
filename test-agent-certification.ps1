# =====================================================================
# Biason - Automation Agent: CERTIFICACAO END-TO-END real
#
# O build e os 309 testes unitarios/integracao ja passaram 100% (rodou
# antes com o test-agent.ps1). Este script vai alem: ele levanta um
# Agent.Service DE VERDADE, conecta ele no seu Portal (que ja esta
# rodando nesta maquina), registra, e manda o Agent executar automacoes
# reais (echo/fail/timeout/cancel/progress/artifact) - o teste mais
# proximo possivel de "o agente esta pronto para rodar automacoes" sem
# ser producao.
#
# PRE-REQUISITO (uma vez so): o harness de certificacao precisa de um
# runtime Python 3.13 "embeddable" do Windows, porque as automacoes de
# certificacao sao em Python e a Deteccao/Download automatico de
# runtime ainda NAO existe no Agent (isso e um gap real que encontrei
# no codigo - ExecutionManager so lanca "Runtime not found" se faltar).
#
#   1) Baixe: https://www.python.org/downloads/windows/
#      -> "Windows embeddable package (64-bit)" de qualquer 3.13.x
#      (arquivo tipo python-3.13.7-embed-amd64.zip)
#   2) Ajuste o caminho abaixo em $pythonArchive para onde voce salvou.
#
# Como usar:
#   powershell -ExecutionPolicy Bypass -File .\test-agent-certification.ps1
# =====================================================================

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot
$logFile = Join-Path $root "certification-run-log.txt"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

# >>> AJUSTE AQUI se o zip do Python estiver em outro lugar <<<
$pythonArchive = Join-Path $root "python-3.13-embed-amd64.zip"

function Log($msg) {
    Write-Host $msg
    Add-Content -Path $logFile -Value $msg
}
function Section($title) {
    Log "`n========== $title =========="
}

$cli = Join-Path $root "automation-agent\tools\Certification.Cli\bin\Release\net8.0\certification.dll"
if (-not (Test-Path $cli)) {
    Log "ERRO: nao achei $cli - rode primeiro o test-agent.ps1 (precisa compilar o Certification.sln antes)."
    exit 1
}

Section "0) Runtime Python de certificacao"
if (Test-Path $pythonArchive) {
    Log "Arquivo encontrado: $pythonArchive"
    $env:CERTIFICATION_RUNTIME_ARCHIVE = $pythonArchive
} else {
    Log "AVISO: nao encontrei $pythonArchive."
    Log "Baixe o 'Windows embeddable package (64-bit)' do Python 3.13 em https://www.python.org/downloads/windows/"
    Log "e salve como '$pythonArchive' (ou edite a variavel `$pythonArchive` no topo deste script)."
    Log "Sem isso, os cenarios de certificacao (que sao scripts Python) devem aparecer como BLOCKED abaixo -"
    Log "o que por si so ja confirma o gap real: o Agent nao baixa runtime sozinho, precisa vir pre-instalado."
}

Push-Location $root

Section "1) certification prepare (sobe/reaproveita o Portal, semeia automacoes de certificacao no Portal)"
$prepareOut = dotnet $cli prepare 2>&1 | Out-String
Log $prepareOut

Section "2) certification start (sobe um Agent.Service real e espera ele registrar/conectar no Portal)"
$startOut = dotnet $cli start 2>&1 | Out-String
Log $startOut

Section "3) certification status"
$statusOut = dotnet $cli status 2>&1 | Out-String
Log $statusOut

Section "4) certification run all (executa echo/fail/timeout/cancel/progress/artifact de verdade)"
$runOut = dotnet $cli run all 2>&1 | Out-String
Log $runOut

Section "5) certification stop (encerra o Agent.Service de certificacao)"
$stopOut = dotnet $cli stop 2>&1 | Out-String
Log $stopOut

Pop-Location

Section "RESUMO"
Log "Log completo: $logFile"
Log "O relatorio JSON de cada rodada fica em automation-agent\certification-runs\<run_id>\report.json"
Log "Me manda o log (ou cola aqui) que eu leio o resultado real."

Write-Host "`n`nPronto! Log completo em: $logFile" -ForegroundColor Green
