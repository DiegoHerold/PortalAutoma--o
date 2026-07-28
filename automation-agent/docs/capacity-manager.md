# Capacity Manager

Gerencia pools de execução e limites de recursos.

## Pools

| Pool | Descrição | Padrão |
|------|-----------|--------|
| `background` | Automações sem interface | 3 slots |
| `browser` | Playwright headless | 1 slot |
| `interactive` | Sessão interativa (Fase 3) | 0 slots |

## Configuração (appsettings.json)

```json
{
  "Capacity": {
    "BackgroundPoolSize": 3,
    "BrowserPoolSize": 1,
    "InteractivePoolSize": 0,
    "SnapshotTtlSeconds": 60
  }
}
```

## Snapshot de Capacidade

```json
{
  "agent_id": "...",
  "revision": 42,
  "pools": {
    "background": {
      "effective_total": 3,
      "used": 1,
      "reserved": 0,
      "available": 2
    },
    "browser": {
      "effective_total": 1,
      "used": 0,
      "reserved": 0,
      "available": 1
    }
  }
}
```

## Reservas de Recursos

Antes da preparação, o Admission Controller reserva um slot. A reserva é liberada quando:

- Execução termina (sucesso ou falha)
- Preparação falha
- Cancelamento
- Timeout da reserva (300s padrão)
- Recuperação após reinício
