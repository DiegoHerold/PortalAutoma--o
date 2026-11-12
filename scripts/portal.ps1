#Requires -Version 5.1
<#
.SYNOPSIS
    Sobe e derruba o Portal de Automacoes nativamente no Windows
    (docs/deployment.md).

.DESCRIPTION
    Processos gerenciados: PostgreSQL dedicado, API (uvicorn), worker e beat
    (Celery) e frontend (Next.js standalone). O Redis roda como servico do
    Windows e nao e iniciado/parado aqui.

    Dados, logs e PIDs ficam fora do repositorio, em PORTAL_DATA_DIR
    (padrao: %LOCALAPPDATA%\PortalAutomacoes).

.EXAMPLE
    .\scripts\portal.ps1 setup           # instala dependencias, .env, banco e build
    .\scripts\portal.ps1 start
    .\scripts\portal.ps1 status
    .\scripts\portal.ps1 stop
    .\scripts\portal.ps1 open-firewall   # libera 3000/8000 para a rede local
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'start', 'stop', 'restart', 'status', 'open-firewall')]
    [string]$Command = 'status'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot 'backend'
$frontendDir = Join-Path $repoRoot 'frontend'
$envFile = Join-Path $backendDir '.env'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'

$dataDir = if ($env:PORTAL_DATA_DIR) { $env:PORTAL_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'PortalAutomacoes' }
$pgData = Join-Path $dataDir 'postgres'
$packagesDir = Join-Path $dataDir 'packages'
$logDir = Join-Path $dataDir 'logs'
$runDir = Join-Path $dataDir 'run'

$apiPort = 8000
$frontendPort = 3000
$managedPgPort = 5433
$tlsCiphers = 'ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!eNULL:!MD5:!DSS'

function Write-Step([string]$Message) {
    Write-Host ">> $Message" -ForegroundColor Cyan
}

function New-Secret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buffer)
    return ([BitConverter]::ToString($buffer) -replace '-', '').ToLowerInvariant()
}

function Read-EnvFile {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
    }
    return $values
}

function Get-LanAddress {
    $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
        Sort-Object { $_.RouteMetric + (Get-NetIPInterface -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4).InterfaceMetric } |
        Select-Object -First 1
    if ($route) {
        $address = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($address) { return $address.IPAddress }
    }
    return 'localhost'
}

function Test-TcpPort([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        return ($connect.AsyncWaitHandle.WaitOne(1000) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-Http([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return ($response.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Wait-Until([scriptblock]$Condition, [string]$Description, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "Timeout aguardando $Description. Veja os logs em $logDir."
}

function Invoke-Native([string]$Exe, [string[]]$Arguments, [string]$WorkingDirectory = $repoRoot) {
    Push-Location $WorkingDirectory
    try {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') falhou (exit $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
}

# -- PostgreSQL dedicado --------------------------------------------------

function Get-PgBin {
    $pgCtl = Get-Command pg_ctl.exe -ErrorAction SilentlyContinue
    if ($pgCtl) { return Split-Path -Parent $pgCtl.Source }
    # So pastas de versao (18, 17...): ha outras ali, como psqlODBC, que nao sao numero.
    $installed = Get-ChildItem 'C:\Program Files\PostgreSQL' -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d+$' } | Sort-Object { [int]$_.Name } -Descending | Select-Object -First 1
    if ($installed) { return Join-Path $installed.FullName 'bin' }
    throw 'PostgreSQL nao encontrado. Instale com: winget install PostgreSQL.PostgreSQL.18'
}

function Test-ManagedPostgres {
    return (Read-EnvFile)['PORTAL_MANAGED_POSTGRES'] -eq 'true'
}

function Test-PostgresPronto {
    # A porta abre antes de o banco aceitar conexoes (ex.: recuperando depois de um desligamento
    # brusco). pg_isready so devolve 0 quando ele aceita.
    & (Join-Path (Get-PgBin) 'pg_isready.exe') -h 127.0.0.1 -p $managedPgPort -q 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Start-ManagedPostgres {
    if (-not (Test-ManagedPostgres)) { return }
    if (-not (Test-TcpPort $managedPgPort)) {
        Write-Step 'Iniciando PostgreSQL dedicado'
        # Sem -w: com -w o pg_ctl herda os handles do terminal e pode nao retornar.
        Start-Process -FilePath (Join-Path (Get-PgBin) 'pg_ctl.exe') -WindowStyle Hidden `
            -ArgumentList @('start', '-D', "`"$pgData`"", '-l', "`"$(Join-Path $logDir 'postgres.log')`"") | Out-Null
        Wait-Until { Test-TcpPort $managedPgPort } 'o PostgreSQL' 30
    }
    # Mesmo com a porta aberta, espera aceitar conexoes antes das migrations.
    Wait-Until { Test-PostgresPronto } 'o PostgreSQL aceitar conexoes (recuperacao)' 120
}

function Stop-ManagedPostgres {
    if (-not (Test-ManagedPostgres)) { return }
    if (-not (Test-TcpPort $managedPgPort)) { return }
    Write-Step 'Parando PostgreSQL dedicado'
    Invoke-Native (Join-Path (Get-PgBin) 'pg_ctl.exe') @('stop', '-D', $pgData, '-m', 'fast', '-w')
}

function Initialize-ManagedPostgres {
    if (-not (Test-ManagedPostgres) -or (Test-Path (Join-Path $pgData 'PG_VERSION'))) { return }

    Write-Step "Criando cluster PostgreSQL dedicado em $pgData (porta $managedPgPort)"
    $config = Read-EnvFile
    $bin = Get-PgBin
    $passwordFile = Join-Path $runDir 'pgpass.tmp'
    [IO.File]::WriteAllText($passwordFile, $config['POSTGRES_PASSWORD'], (New-Object Text.UTF8Encoding $false))
    try {
        Invoke-Native (Join-Path $bin 'initdb.exe') @(
            '-D', $pgData, '-U', $config['POSTGRES_USER'], '-A', 'scram-sha-256',
            "--pwfile=$passwordFile", '-E', 'UTF8', '--locale=C')
    } finally {
        Remove-Item -LiteralPath $passwordFile -Force -ErrorAction SilentlyContinue
    }
    Add-Content -LiteralPath (Join-Path $pgData 'postgresql.conf') -Value "`nport = $managedPgPort`nlisten_addresses = '127.0.0.1'"

    Start-ManagedPostgres
    $env:PGPASSWORD = $config['POSTGRES_PASSWORD']
    try {
        Invoke-Native (Join-Path $bin 'createdb.exe') @(
            '-h', '127.0.0.1', '-p', "$managedPgPort", '-U', $config['POSTGRES_USER'], $config['POSTGRES_DB'])
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

# -- TLS ------------------------------------------------------------------

# Certificado emitido pela CA da empresa (cadeia completa em PEM) e a chave.
# Com os dois no backend\.env a API sobe so em HTTPS (TLS 1.2 ou superior).
function Get-TlsSettings {
    if (-not (Test-Path $envFile)) { return $null }
    $values = Read-EnvFile
    $cert = $values['PORTAL_TLS_CERT']
    $key = $values['PORTAL_TLS_KEY']
    if (-not $cert -and -not $key) { return $null }
    if (-not $cert -or -not $key) { throw 'Defina PORTAL_TLS_CERT e PORTAL_TLS_KEY juntos no backend\.env.' }
    foreach ($file in @($cert, $key)) {
        if (-not (Test-Path -LiteralPath $file)) { throw "Arquivo TLS nao encontrado: $file" }
    }
    $publicUrl = $values['BACKEND_PUBLIC_URL']
    if (-not $publicUrl -or -not $publicUrl.StartsWith('https://')) {
        throw 'Com TLS, BACKEND_PUBLIC_URL precisa ser https:// com o nome que esta no certificado.'
    }
    return @{ Cert = $cert; Key = $key; PublicUrl = $publicUrl.TrimEnd('/') }
}

# Com TLS, o health check usa o nome do certificado: a validacao nunca e desligada.
function Get-ApiHealthUrl {
    $tls = Get-TlsSettings
    if ($tls) { return "$($tls.PublicUrl)/health" }
    return "http://127.0.0.1:$apiPort/health"
}

# -- Setup ----------------------------------------------------------------

function Initialize-EnvFile {
    if (Test-Path $envFile) {
        Write-Step 'backend\.env ja existe; mantendo'
        return
    }
    Write-Step 'Gerando backend\.env'
    $lan = Get-LanAddress
    $overrides = @{
        'SECRET_KEY'                = New-Secret
        'POSTGRES_PASSWORD'         = New-Secret 24
        'POSTGRES_PORT'             = "$managedPgPort"
        'LOCAL_STORAGE_PATH'        = $packagesDir
        'BACKEND_PUBLIC_URL'        = "http://${lan}:$apiPort"
    }
    $lines = foreach ($line in Get-Content -LiteralPath (Join-Path $backendDir '.env.example') -Encoding UTF8) {
        if ($line -match '^([A-Z_0-9]+)=' -and $overrides.ContainsKey($Matches[1])) {
            "$($Matches[1])=$($overrides[$Matches[1]])"
        } else {
            $line
        }
    }
    $text = (@($lines) + @('', '# Cluster dedicado criado e iniciado por scripts/portal.ps1.', 'PORTAL_MANAGED_POSTGRES=true', '')) -join "`n"
    # Sem BOM: um BOM viraria parte do nome da primeira variavel.
    [IO.File]::WriteAllText($envFile, $text, (New-Object Text.UTF8Encoding $false))
}

function Install-BackendDependencies {
    if (-not (Test-Path $python)) {
        Write-Step 'Criando virtualenv do backend (Python 3.12)'
        Invoke-Native 'py' @('-3.12', '-m', 'venv', (Join-Path $backendDir '.venv'))
    }
    Write-Step 'Instalando dependencias do backend'
    Invoke-Native $python @('-m', 'pip', 'install', '--quiet', '--disable-pip-version-check', '-r', 'requirements\dev.txt') $backendDir
}

function Build-Frontend {
    Write-Step 'Instalando dependencias do frontend'
    Invoke-Native 'npm.cmd' @('ci', '--include=dev', '--no-audit', '--no-fund') $frontendDir
    Write-Step 'Gerando build do frontend'
    Invoke-Native 'npm.cmd' @('run', 'build') $frontendDir

    # output: "standalone" nao copia _next/static nem public/ sozinho; sem isso
    # todo chunk JS/CSS responde 404 e a pagina quebra com ChunkLoadError.
    $standalone = Join-Path $frontendDir '.next\standalone'
    $staticTarget = Join-Path $standalone '.next\static'
    if (Test-Path $staticTarget) { Remove-Item -LiteralPath $staticTarget -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $frontendDir '.next\static') -Destination $staticTarget -Recurse
    $public = Join-Path $frontendDir 'public'
    if (Test-Path $public) { Copy-Item -LiteralPath $public -Destination $standalone -Recurse -Force }
}

function Invoke-Setup {
    foreach ($directory in @($dataDir, $packagesDir, $logDir, $runDir)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    Install-BackendDependencies
    Initialize-EnvFile
    Initialize-ManagedPostgres
    Build-Frontend
    Write-Step 'Setup concluido. Suba o portal com: .\scripts\portal.ps1 start'
}

# -- Processos ------------------------------------------------------------

function Get-ProcessDefinitions {
    $schedule = Join-Path $runDir 'celerybeat-schedule'
    $apiArguments = "-m uvicorn main:app --host 0.0.0.0 --port $apiPort"
    $tls = Get-TlsSettings
    # O padrao do uvicorn (--ssl-ciphers TLSv1) so oferece cifras CBC com SHA-1: um cliente
    # TLS 1.2 moderno nao negocia. Aqui so AEAD com troca de chave efemera.
    if ($tls) { $apiArguments += " --ssl-certfile `"$($tls.Cert)`" --ssl-keyfile `"$($tls.Key)`" --ssl-ciphers `"$tlsCiphers`"" }
    return @(
        @{ Name = 'api'; File = $python; Directory = $backendDir
           Arguments = $apiArguments }
        # prefork nao funciona no Windows; threads mantem tarefas concorrentes.
        @{ Name = 'worker'; File = $python; Directory = $backendDir
           Arguments = '-m celery -A workers.celery_app.celery_app worker --loglevel=info --pool=threads --concurrency=4 -Q critical,high,normal,low' }
        # Sem o beat, Schedules sao apenas cadastro e nada dispara sozinho.
        @{ Name = 'beat'; File = $python; Directory = $backendDir
           Arguments = "-m celery -A workers.celery_app.celery_app beat --loglevel=info --schedule=`"$schedule`"" }
        @{ Name = 'frontend'; File = 'node'; Directory = (Join-Path $frontendDir '.next\standalone')
           Arguments = 'server.js' }
    )
}

function Get-ManagedProcess([string]$Name) {
    $pidFile = Join-Path $runDir "$Name.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    $process = Get-Process -Id ([int](Get-Content -LiteralPath $pidFile)) -ErrorAction SilentlyContinue
    # O Windows reutiliza PIDs: so confia se ainda for python/node.
    if ($process -and $process.ProcessName -in @('python', 'node')) { return $process }
    Remove-Item -LiteralPath $pidFile -Force
    return $null
}

function Start-ManagedProcess([hashtable]$Definition) {
    $name = $Definition.Name
    if (Get-ManagedProcess $name) {
        Write-Step "$name ja esta rodando"
        return
    }
    Write-Step "Iniciando $name"
    $process = Start-Process -FilePath $Definition.File -ArgumentList $Definition.Arguments `
        -WorkingDirectory $Definition.Directory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $logDir "$name.out.log") `
        -RedirectStandardError (Join-Path $logDir "$name.err.log")
    Set-Content -LiteralPath (Join-Path $runDir "$name.pid") -Value $process.Id -Encoding Ascii
}

function Stop-ManagedProcess([string]$Name) {
    $process = Get-ManagedProcess $Name
    if ($process) {
        Write-Step "Parando $Name"
        & taskkill.exe /PID $process.Id /T /F | Out-Null
    }
    Remove-Item -LiteralPath (Join-Path $runDir "$Name.pid") -Force -ErrorAction SilentlyContinue
}

function Assert-Installed {
    if (-not (Test-Path $python) -or -not (Test-Path $envFile) -or
        -not (Test-Path (Join-Path $frontendDir '.next\standalone\server.js'))) {
        throw 'Portal ainda nao instalado. Rode primeiro: .\scripts\portal.ps1 setup'
    }
}

function Assert-Redis {
    if (Test-TcpPort 6379) { return }
    $service = Get-Service -Name Redis -ErrorAction SilentlyContinue
    if ($service) {
        Write-Step 'Iniciando servico Redis'
        Start-Service -Name Redis
        Wait-Until { Test-TcpPort 6379 } 'o Redis' 15
        return
    }
    throw 'Redis nao encontrado na porta 6379. Instale com: winget install Redis.Redis'
}

function Invoke-Start {
    Assert-Installed
    foreach ($directory in @($logDir, $runDir)) { New-Item -ItemType Directory -Force -Path $directory | Out-Null }

    Start-ManagedPostgres
    Assert-Redis

    Write-Step 'Aplicando migrations'
    $env:PYTHONPATH = $backendDir
    Invoke-Native $python @('-m', 'alembic', 'upgrade', 'head') $backendDir

    $env:PYTHONUNBUFFERED = '1'
    $env:NODE_ENV = 'production'
    $env:HOSTNAME = '0.0.0.0'
    $env:PORT = "$frontendPort"
    foreach ($definition in Get-ProcessDefinitions) { Start-ManagedProcess $definition }

    $apiHealth = Get-ApiHealthUrl
    Wait-Until { Test-Http $apiHealth } 'a API' 60
    Wait-Until { Test-Http "http://127.0.0.1:$frontendPort/" } 'o frontend' 60

    $lan = Get-LanAddress
    Write-Host ''
    Write-Host "Portal no ar: http://localhost:$frontendPort (rede local: http://${lan}:$frontendPort)" -ForegroundColor Green
    if (Get-TlsSettings) {
        Write-Host "API em HTTPS: $((Get-TlsSettings).PublicUrl)" -ForegroundColor Green
    } else {
        Write-Host 'ATENCAO: API em HTTP, sem TLS. O modo direto do SDK recusa http://. Defina PORTAL_TLS_CERT e PORTAL_TLS_KEY no backend\.env.' -ForegroundColor Yellow
    }
    Write-Host "Logs: $logDir"
}

function Invoke-Stop {
    foreach ($definition in Get-ProcessDefinitions) { Stop-ManagedProcess $definition.Name }
    Stop-ManagedPostgres
}

function Show-Status {
    $database = if (Test-Path $envFile) { [int](Read-EnvFile)['POSTGRES_PORT'] } else { $managedPgPort }
    $checks = [ordered]@{
        'postgres' = Test-TcpPort $database
        'redis'    = Test-TcpPort 6379
        'api'      = Test-Http (Get-ApiHealthUrl)
        'worker'   = [bool](Get-ManagedProcess 'worker')
        'beat'     = [bool](Get-ManagedProcess 'beat')
        'frontend' = Test-Http "http://127.0.0.1:$frontendPort/"
    }
    foreach ($check in $checks.GetEnumerator()) {
        $state = if ($check.Value) { 'UP' } else { 'DOWN' }
        Write-Host ('{0,-10}{1}' -f $check.Key, $state)
    }
    return (@($checks.Values) -notcontains $false)
}

function Open-Firewall {
    $ruleName = 'Portal de Automacoes (rede local)'
    if (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue) {
        Write-Step 'Regra de firewall ja existe'
        return
    }
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $frontendPort, $apiPort -RemoteAddress LocalSubnet -Profile Private, Domain | Out-Null
    Write-Step "Portas $frontendPort e $apiPort liberadas para a subrede local"
}

switch ($Command) {
    'setup'         { Invoke-Setup }
    'start'         { Invoke-Start }
    'stop'          { Invoke-Stop }
    'restart'       { Invoke-Stop; Invoke-Start }
    'open-firewall' { Open-Firewall }
    'status'        { if (-not (Show-Status)) { exit 1 } }
}
