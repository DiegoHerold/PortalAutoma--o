# Estrutura Local de Dados

## Diretórios

```
C:\ProgramData\BiasonAutomationAgent\
├── config\          # Configuração local
├── database\
│   └── agent.db     # SQLite principal
├── store\
│   ├── runtimes\    # Runtimes (fases futuras)
│   └── packages\    # Pacotes de automação (fases futuras)
├── downloads\       # Downloads temporários
├── staging\         # Staging de preparação
├── executions\      # Dados de execuções ativas
├── artifacts\       # Artefatos gerados
├── spool\           # Fila local offline
├── diagnostics\     # Exportações de diagnóstico
└── logs\            # Logs estruturados
```

## Configuração alternativa

Para desenvolvimento, defina `AUTOMATION_AGENT_DATA_DIR` ou configure em `appsettings.json`:

```json
{
  "Development": {
    "DataDirectory": "C:\\dev\\agent-data"
  }
}
```

## Criação

Os diretórios são criados de forma idempotente na inicialização.
Dados existentes nunca são apagados automaticamente.
