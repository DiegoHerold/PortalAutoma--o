# Configuração

## Seções

| Seção | Descrição |
|-------|-----------|
| Agent | Nome, perfil, versão |
| Storage | Espaço mínimo em disco |
| Monitoring | Intervalo de coleta, retenção |
| MachineProfiler | Intervalo de refresh do perfil |
| Database | Timeout, journal mode |
| AgentLogging | Tamanho máximo de log, retenção |
| Development | Diretório alternativo, console logging |

## Fontes (em ordem de precedência)

1. Variáveis de ambiente com prefixo `AUTOMATION_AGENT_`
2. `appsettings.{Environment}.json`
3. `appsettings.json`
4. Valores padrão no código

## Validação

Todas as opções são validadas na inicialização. Valores inválidos geram log de erro e podem impedir a inicialização.
