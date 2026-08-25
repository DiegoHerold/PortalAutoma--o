# =====================================================================
# Biason - Provisiona os runtimes de VERDADE que faltam no Agent
#
# O Agent (RuntimeLauncher.cs) so sabe executar 6 tipos de entrypoint:
#   python_function, python_module, powershell_script, executable,
#   browser_playwright, python_desktop
#
# powershell_script e executable NAO precisam de runtime baixado (usam
# o powershell/executavel ja instalados/empacotados). python_function
# ja tem o runtime "python-core-3.13" pronto (voce ja provou isso
# funcionando). Mas dois runtimes que voce pediu explicitamente ainda
# nao existem no disco:
#
#   - python-browser-3.13-playwright  -> pro entrypoint browser_playwright
#     (navegador de verdade via Playwright). Sem isso o Agent falha ANTES
#     de tentar rodar, com "Runtime not found: python-browser:3.13-playwright".
#
#   - python-desktop-3.13             -> pro entrypoint python_desktop
#     (automacao de aplicativo VISIVEL/interativa, com pyautogui/pywinauto
#     controlando mouse/teclado numa janela real).
#
# Este script clona o python-core-3.13 (que ja tem um python.exe
# funcionando) pra cada um desses dois, habilita pip nele (Python
# embeddable vem com pip DESABILITADO por padrao) e instala os pacotes
# que cada um precisa. Precisa de internet nesta maquina (baixa pip,
# playwright, e o proprio Chromium do Playwright).
#
# Como usar (depois que certification prepare/start ja rodou pelo menos
# uma vez, pra python-core-3.13 existir):
#   powershell -ExecutionPolicy Bypass -File .\provision-runtimes.ps1
# =====================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$logFile = Join-Path $root "provision-runtimes-log.txt"
if (Test-Path $logFile) { Remove-Item $logFile -Force }

function Log($msg) {
    Write-Host $msg
    Add-Content -Path $logFile -Value $msg
}

function Section($title) {
    Log "`n========== $title =========="
}

$runtimesRoot = Join-Path $root "automation-agent\certification-runs\agent-data\store\runtimes"
$sourceDir = Join-Path $runtimesRoot "python-core-3.13"

Section "0) Verificando pre-requisito: python-core-3.13"
if (-not (Test-Path (Join-Path $sourceDir "python.exe"))) {
    Log "ERRO: nao encontrei $sourceDir\python.exe."
    Log "Rode 'certification prepare' (ou o test-agent-all-runtimes.ps1, que ja faz isso)"
    Log "pelo menos uma vez antes deste script - e ele que baixa/prepara o python-core-3.13"
    Log "que este script clona para os outros dois runtimes."
    exit 1
}
Log "OK: $sourceDir encontrado."

# Habilita pip numa copia de um Python embeddable (pip vem desligado por
# padrao nessa distribuicao - normalmente so tem python.exe + .pyd + a
# stdlib zipada). Receita padrao: descomentar "import site" no arquivo
# ._pth (senao o embeddable ignora Lib\site-packages inteiro) e rodar o
# get-pip.py oficial.
function Enable-EmbeddablePip {
    param([string]$Dir)

    $pthFile = Get-ChildItem -Path $Dir -Filter "python3*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pthFile) {
        throw "Nao encontrei o arquivo *._pth em $Dir (esperado numa distribuicao Python embeddable)."
    }

    $content = Get-Content $pthFile.FullName
    $newContent = $content -replace '^#\s*import site', 'import site'
    Set-Content -Path $pthFile.FullName -Value $newContent
    Log "  ._pth ajustado: $($pthFile.Name) (import site habilitado)"

    $getPipPath = Join-Path $Dir "get-pip.py"
    if (-not (Test-Path (Join-Path $Dir "Lib\site-packages\pip"))) {
        Log "  Baixando get-pip.py..."
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPipPath -UseBasicParsing
        Log "  Instalando pip..."
        & "$Dir\python.exe" $getPipPath --no-warn-script-location 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
        if ($LASTEXITCODE -ne 0) { throw "get-pip.py falhou (exit code $LASTEXITCODE)" }
        Remove-Item $getPipPath -Force -ErrorAction SilentlyContinue
    } else {
        Log "  pip ja estava instalado, pulando."
    }
}

function Clone-Runtime {
    param([string]$TargetDir, [string]$Label)

    if (Test-Path (Join-Path $TargetDir "python.exe")) {
        Log "$Label ja existe em $TargetDir - pulando clone (apague a pasta pra reprovisionar do zero)."
        return
    }
    Log "Clonando python-core-3.13 -> $Label ($TargetDir)..."
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    # /E copia subpastas (inclusive vazias), /NFL /NDL /NJH /NJS deixam o
    # log do robocopy enxuto (senao lista cada .pyd/.dll individualmente).
    robocopy $sourceDir $TargetDir /E /NFL /NDL /NJH /NJS | Out-Null
    if (-not (Test-Path (Join-Path $TargetDir "python.exe"))) {
        throw "robocopy nao produziu um python.exe em $TargetDir - clone falhou."
    }
    Log "  Clonado com sucesso."
}

Section "1) Runtime python-browser-3.13-playwright (entrypoint browser_playwright)"
$browserDir = Join-Path $runtimesRoot "python-browser-3.13-playwright"
$browserOk = $true
try {
    Clone-Runtime -TargetDir $browserDir -Label "python-browser-3.13-playwright"
    Enable-EmbeddablePip -Dir $browserDir

    if (-not (Test-Path (Join-Path $browserDir "Lib\site-packages\playwright"))) {
        Log "  Instalando pacote 'playwright'..."
        & "$browserDir\python.exe" -m pip install playwright --no-warn-script-location 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
        if ($LASTEXITCODE -ne 0) { throw "pip install playwright falhou (exit code $LASTEXITCODE)" }
    } else {
        Log "  Pacote 'playwright' ja instalado."
    }

    # RuntimeLauncher.BuildBrowserPlaywright aponta PLAYWRIGHT_BROWSERS_PATH
    # para "<RuntimePath>\browsers" - o Chromium tem que estar baixado
    # exatamente ali pra a automacao real encontrar o navegador.
    $browsersSubdir = Join-Path $browserDir "browsers"
    $env:PLAYWRIGHT_BROWSERS_PATH = $browsersSubdir
    if (-not (Test-Path $browsersSubdir) -or (Get-ChildItem $browsersSubdir -ErrorAction SilentlyContinue).Count -eq 0) {
        Log "  Baixando Chromium (playwright install chromium)... isso pode demorar alguns minutos."
        & "$browserDir\python.exe" -m playwright install chromium 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
        if ($LASTEXITCODE -ne 0) { throw "playwright install chromium falhou (exit code $LASTEXITCODE)" }
    } else {
        Log "  Chromium ja baixado em $browsersSubdir."
    }
    Remove-Item Env:\PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue

    Log "`n>>> python-browser-3.13-playwright: READY"
} catch {
    $browserOk = $false
    Log "`n>>> python-browser-3.13-playwright: FALHOU - $_"
}

Section "2) Runtime python-desktop-3.13 (entrypoint python_desktop - automacao de aplicativo VISIVEL)"
$desktopDir = Join-Path $runtimesRoot "python-desktop-3.13"
$desktopOk = $true
try {
    Clone-Runtime -TargetDir $desktopDir -Label "python-desktop-3.13"
    Enable-EmbeddablePip -Dir $desktopDir

    # Regressao encontrada na 1a rodada: pip parou logo apos "Getting
    # requirements to build wheel: finished with status 'done'" com um
    # "ERROR: Exception:" sem detalhe nenhum - esse formato e o proprio pip
    # engolindo uma excecao interna sem mensagem, tipico de duas causas
    # reais aqui: (a) um .tar.gz antigo de pyautogui ja em cache local
    # (%LOCALAPPDATA%\pip\cache) fazendo o pip tentar compilar do FONTE em
    # vez de baixar o wheel pronto, e (b) pacotes com setup.py antigo que
    # importam "distutils" - removido da stdlib no Python 3.12+ (PEP 632),
    # entao qualquer sdist velho quebra a build silenciosamente. Corrigido
    # instalando cada pacote separado (isola qual falha), sem cache
    # (--no-cache-dir, ignora sdist velho) e so aceitando wheel pronto
    # (--only-binary=:all:, nunca tenta compilar do fonte) - se mesmo assim
    # nao existir wheel pra algum pacote, o pip agora falha com uma
    # mensagem de verdade ("no matching distribution") em vez de um
    # "Exception:" mudo.
    Log "  Atualizando pip/setuptools/wheel..."
    & "$desktopDir\python.exe" -m pip install --upgrade pip setuptools wheel --no-warn-script-location 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
    if ($LASTEXITCODE -ne 0) { throw "upgrade de pip/setuptools/wheel falhou (exit code $LASTEXITCODE)" }

    foreach ($pkg in @("pyautogui", "pywinauto")) {
        if (Test-Path (Join-Path $desktopDir "Lib\site-packages\$pkg")) {
            Log "  Pacote '$pkg' ja instalado."
            continue
        }
        Log "  Instalando pacote '$pkg' (so wheel pronto, sem cache)..."
        & "$desktopDir\python.exe" -m pip install $pkg --no-cache-dir --only-binary=:all: --no-warn-script-location 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
        if ($LASTEXITCODE -ne 0) {
            Log "  '$pkg' nao tem wheel pronto pra esta plataforma/versao de Python - tentando de novo permitindo compilar do fonte, com saida detalhada (-v) pra ver o erro real..."
            & "$desktopDir\python.exe" -m pip install $pkg --no-cache-dir -v --no-warn-script-location 2>&1 | ForEach-Object { Add-Content -Path $logFile -Value $_ }
            if ($LASTEXITCODE -ne 0) { throw "pip install $pkg falhou mesmo permitindo compilar do fonte (exit code $LASTEXITCODE) - veja $logFile para o erro detalhado (-v)" }
        }
    }

    Log "`n>>> python-desktop-3.13: READY"
} catch {
    $desktopOk = $false
    Log "`n>>> python-desktop-3.13: FALHOU - $_"
}

Section "RESUMO"
Log ("python-browser-3.13-playwright: " + $(if ($browserOk) { "READY" } else { "FALHOU" }))
Log ("python-desktop-3.13:            " + $(if ($desktopOk) { "READY" } else { "FALHOU" }))
Log "`nLog completo salvo em: $logFile"

if (-not $browserOk -or -not $desktopOk) { exit 1 }
exit 0
