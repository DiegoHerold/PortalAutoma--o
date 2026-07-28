# Windows Service

## Publicação autocontida

```powershell
dotnet publish src/Agent.Service/Agent.Service.csproj `
    --configuration Release `
    --runtime win-x64 `
    --self-contained true `
    -p:PublishSingleFile=true
```

O executável resultante não requer .NET Runtime instalado.

## Instalação manual

```powershell
sc.exe create BiasonAutomationAgent binPath= "C:\path\AgentService.exe" start= delayed-auto
sc.exe description BiasonAutomationAgent "Automation Agent for Biason"
sc.exe failure BiasonAutomationAgent reset= 86400 actions= restart/60000/restart/120000/restart/300000
```

## Controle

```powershell
sc.exe start BiasonAutomationAgent
sc.exe stop BiasonAutomationAgent
sc.exe query BiasonAutomationAgent
sc.exe delete BiasonAutomationAgent
```
