# Script para encontrar e matar processos travando o build

Write-Host "=== Procurando processos do Node.js e Next.js ===" -ForegroundColor Cyan

# Procurar processos do Node
$nodeProcesses = Get-Process -Name "node" -ErrorAction SilentlyContinue

if ($nodeProcesses) {
    Write-Host "`nProcessos Node.js encontrados:" -ForegroundColor Yellow
    $nodeProcesses | Format-Table Id, ProcessName, CPU, WorkingSet, StartTime -AutoSize
    
    Write-Host "`nDeseja matar TODOS os processos Node.js? (S/N): " -ForegroundColor Red -NoNewline
    $response = Read-Host
    
    if ($response -eq "S" -or $response -eq "s") {
        foreach ($proc in $nodeProcesses) {
            try {
                Stop-Process -Id $proc.Id -Force
                Write-Host "Processo $($proc.Id) finalizado" -ForegroundColor Green
            } catch {
                Write-Host "Erro ao finalizar processo $($proc.Id): $_" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "`nNenhum processo Node.js encontrado" -ForegroundColor Green
}

# Verificar se há arquivos travados na pasta .next
Write-Host "`n=== Verificando arquivos travados ===" -ForegroundColor Cyan

$nextPath = Join-Path $PSScriptRoot ".next"
if (Test-Path $nextPath) {
    Write-Host "Pasta .next existe. Tentando descobrir qual processo está usando..." -ForegroundColor Yellow
    
    # Usar handle.exe se disponível (do Sysinternals)
    $handlePath = "C:\Windows\System32\handle.exe"
    if (Test-Path $handlePath) {
        Write-Host "`nProcessos usando arquivos em .next:" -ForegroundColor Yellow
        & $handlePath -accepteula $nextPath 2>$null
    } else {
        Write-Host "`nDica: Instale Sysinternals Handle para ver processos específicos" -ForegroundColor Yellow
        Write-Host "Download: https://learn.microsoft.com/en-us/sysinternals/downloads/handle" -ForegroundColor Gray
    }
}

Write-Host "`n=== Processos em execução relacionados ao Portal ===" -ForegroundColor Cyan
Get-Process | Where-Object {$_.ProcessName -match "node|next|python|uvicorn"} | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize

Write-Host "`nPara matar um processo específico, use: Stop-Process -Id <ID> -Force" -ForegroundColor Yellow
