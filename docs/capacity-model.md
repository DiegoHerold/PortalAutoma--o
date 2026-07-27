# Modelo de Capacidade

Status: vigente.

Separe os conceitos abaixo.

## MachineProfile

Configuracao fisica e logica detectada:

- CPU e nucleos.
- Memoria.
- Disco.
- Sistema e arquitetura.
- Sessao interativa.
- Softwares.
- Rede.

## AgentRecommendation

Capacidade recomendada calculada pelo Agent:

```json
{
  "interactive": 1,
  "background": 2,
  "browser": 2
}
```

## AdministratorPolicy

Limites manuais definidos pelo administrador. Heartbeat e descoberta local nao
podem sobrescrever politica administrativa.

## CurrentCapacity

Disponibilidade momentanea:

```text
limite efetivo
- execucoes atuais
- ofertas reservadas
- locks
- recursos indisponiveis
```

## HistoricalCapacity

Historico observado de consumo e sucesso.

Todo snapshot deve conter:

- `observed_at`
- `agent_instance_id`
- `revision`
- `ttl`

Scheduler nao usa snapshot expirado como capacidade atual.

## Pools iniciais

- `interactive`
- `background`
- `browser`

Cada pool contem:

- `recommended_total`
- `administrator_total`
- `effective_total`
- `used`
- `reserved`
- `available`

```json
{
  "interactive": {
    "recommended_total": 1,
    "administrator_total": 1,
    "effective_total": 1,
    "used": 0,
    "reserved": 1,
    "available": 0
  }
}
```

Ofertas aceitas tambem reservam capacidade.

