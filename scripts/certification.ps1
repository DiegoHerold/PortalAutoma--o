#Requires -Version 5.1
<#
.SYNOPSIS
    Single entry point for the Portal-Agent certification harness
    (docs/certification-harness.md, docs/runbooks/portal-agent-certification.md).

.DESCRIPTION
    Thin wrapper around `dotnet run --project automation-agent/tools/Certification.Cli`.
    Exists so the whole harness can be driven with one command instead of a
    list of manual steps (docs/certification-harness.md item 76).

.EXAMPLE
    .\scripts\certification.ps1 prepare
    .\scripts\certification.ps1 start
    .\scripts\certification.ps1 status
    .\scripts\certification.ps1 run background
    .\scripts\certification.ps1 run all
    .\scripts\certification.ps1 run echo
    .\scripts\certification.ps1 run fail
    .\scripts\certification.ps1 run timeout
    .\scripts\certification.ps1 run cancel
    .\scripts\certification.ps1 stop
    .\scripts\certification.ps1 clean

.EXAMPLE
    # Full certification in one line (prepare -> start -> run all -> stop):
    .\scripts\certification.ps1 full
#>

param(
    [Parameter(Position = 0)]
    [ValidateSet('prepare', 'start', 'status', 'run', 'stop', 'clean', 'full')]
    [string]$Command = 'status',

    [Parameter(Position = 1)]
    [string]$Scenario = 'all',

    [switch]$PurgeRuntime,
    [switch]$PurgeReports
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$cliProject = Join-Path $repoRoot 'automation-agent\tools\Certification.Cli\Certification.Cli.csproj'

if (-not (Test-Path $cliProject)) {
    throw "Certification.Cli project not found at $cliProject. Run this script from the repository (or a checkout of it)."
}

function Invoke-Certification {
    param([string[]]$CliArgs)
    Write-Host ">> dotnet run --project Certification.Cli -- $($CliArgs -join ' ')" -ForegroundColor Cyan
    & dotnet run --project $cliProject --no-launch-profile -- @CliArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "certification $($CliArgs[0]) exited with code $LASTEXITCODE" -ForegroundColor Yellow
    }
    return $LASTEXITCODE
}

switch ($Command) {
    'prepare' { exit (Invoke-Certification @('prepare')) }
    'start'   { exit (Invoke-Certification @('start')) }
    'status'  { exit (Invoke-Certification @('status')) }
    'run'     { exit (Invoke-Certification @('run', $Scenario)) }
    'stop'    { exit (Invoke-Certification @('stop')) }
    'clean' {
        $cleanArgs = @('clean')
        if ($PurgeRuntime) { $cleanArgs += '--purge-runtime' }
        if ($PurgeReports) { $cleanArgs += '--purge-reports' }
        exit (Invoke-Certification $cleanArgs)
    }
    'full' {
        $exit = Invoke-Certification @('prepare')
        if ($exit -ne 0) { Write-Host 'prepare failed/blocked; stopping.' -ForegroundColor Red; exit $exit }

        $exit = Invoke-Certification @('start')
        if ($exit -ne 0) { Write-Host 'start failed/blocked; stopping.' -ForegroundColor Red; exit $exit }

        $exit = Invoke-Certification @('run', $Scenario)

        Invoke-Certification @('stop') | Out-Null
        exit $exit
    }
}
