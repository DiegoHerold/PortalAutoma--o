<#
    Biason - Demo PowerShell: Conferencia de Certidoes

    Automacao real de demonstracao: le uma lista de certidoes (via
    input.json, se o Portal enviar parametros), "confere" cada uma com um
    pequeno delay para simular trabalho real, reporta progresso via stdout
    e escreve um relatorio como artefato - exatamente o mesmo caminho que
    uma automacao powershell_script real percorreria no Agent (sem
    depender de nenhum runtime baixado: usa o PowerShell ja instalado na
    maquina).
#>

$ErrorActionPreference = "Stop"

$workspace = $env:AUTOMATION_WORKSPACE
if (-not $workspace) { $workspace = (Get-Location).Path }

$artifactsPath = $env:AUTOMATION_ARTIFACTS_PATH
if (-not $artifactsPath) { $artifactsPath = Join-Path $workspace "artifacts" }
New-Item -ItemType Directory -Force -Path $artifactsPath | Out-Null

$documentos = @(
    "certidao_negativa_federal.pdf",
    "certidao_negativa_estadual.pdf",
    "certidao_negativa_municipal.pdf",
    "certidao_fgts.pdf",
    "certidao_trabalhista.pdf"
)

$inputPath = Join-Path $workspace "input\input.json"
if (Test-Path $inputPath) {
    try {
        $inputData = Get-Content -Raw -Path $inputPath | ConvertFrom-Json
        if ($inputData.documentos) { $documentos = $inputData.documentos }
    } catch {
        Write-Output "[Biason] Aviso: nao consegui ler input.json ($($_.Exception.Message)), usando lista padrao."
    }
}

$total = $documentos.Count
Write-Output "[Biason] Iniciando conferencia de $total certidao(oes)..."

$resultados = @()
for ($i = 0; $i -lt $total; $i++) {
    $doc = $documentos[$i]
    Write-Output "[Biason] Conferindo $($i + 1)/${total}: $doc"
    Start-Sleep -Seconds 1
    $resultados += [PSCustomObject]@{
        documento    = $doc
        status       = "conferido"
        conferido_em = (Get-Date).ToUniversalTime().ToString("o")
    }
    $pct = [Math]::Floor((($i + 1) * 100) / $total)
    Write-Output "[Biason] Progresso: $($i + 1)/$total ($pct%)"
}

$reportPath = Join-Path $artifactsPath "relatorio_conferencia_certidoes.txt"
$lines = @(
    "Biason Assessoria Empresarial",
    "Relatorio de Conferencia de Certidoes (demo)",
    "=============================================",
    "",
    "Executado em: $((Get-Date).ToUniversalTime().ToString("o"))",
    "Total de certidoes: $total",
    ""
)
foreach ($r in $resultados) {
    $lines += "  - $($r.documento): $($r.status) ($($r.conferido_em))"
}
Set-Content -Path $reportPath -Value $lines -Encoding UTF8

Write-Output "[Biason] Relatorio gravado em $reportPath"
Write-Output "[Biason] Conferencia concluida com sucesso."

exit 0
