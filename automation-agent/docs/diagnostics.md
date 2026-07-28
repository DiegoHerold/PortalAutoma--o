# Diagnóstico

## Comando

```bash
AgentService.exe diagnostics
```

## Conteúdo exportado

```
diagnostics/diag-{timestamp}/
├── agent-info.json           # Identidade (sem segredos)
├── machine-profile.json      # Perfil da máquina
├── health.json               # Resultado dos health checks
├── database-summary.json     # Tamanho e status do banco
├── configuration-summary.json # Configuração (sem credenciais)
└── recent-logs/              # Últimos 3 arquivos de log
```

## Segurança

Nunca inclui: senhas, tokens, segredos, conteúdo de credenciais, dados pessoais.
