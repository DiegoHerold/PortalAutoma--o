# Guia de Desenvolvimento

## Pré-requisitos

- .NET 8 SDK

## Compilar

```bash
dotnet build AutomationAgent.sln
```

## Testar

```bash
dotnet test AutomationAgent.sln
```

Ou via script:

```powershell
.\scripts\run-tests.ps1
```

## Executar como console

```bash
# Usando diretório alternativo para não escrever em ProgramData
set AUTOMATION_AGENT_DATA_DIR=C:\dev\agent-data
dotnet run --project src/Agent.Service
```

## Gerar relatório da máquina

```bash
dotnet run --project src/Agent.Service -- profile
```

## Exportar diagnóstico

```bash
dotnet run --project src/Agent.Service -- diagnostics
```

## Publicar

```powershell
.\scripts\publish.ps1
```

## Instalar como serviço (desenvolvimento)

```powershell
# Requer privilégio de administrador
.\scripts\install-service.ps1
.\scripts\start-service.ps1
```

## Remover serviço

```powershell
.\scripts\stop-service.ps1
.\scripts\remove-service.ps1
```
