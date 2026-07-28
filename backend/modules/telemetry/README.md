# Telemetry

Ownership: eventos, logs, progresso, metricas, sequencias, deduplicacao, ACK,
deteccao de lacunas, timeline e realtime.

Legado a migrar:

- `app/models/log.py`
- `app/api/v1/endpoints/realtime.py` — ainda é o único canal de tempo real
  consumido pelo frontend hoje (WebSocket `/ws/executions`); o substituto
  oficial já existe (`GET /{execution_id}/stream`, SSE, neste módulo), falta
  religar o frontend e então remover o WebSocket antigo.

Removido (Fase de remoção do legado): `app/services/realtime_service.py`,
`app/services/websocket_broadcaster.py` — sem consumidores (o endpoint antigo
implementa seu próprio `ConnectionManager` inline e nunca usou estes
arquivos).

Telemetry nao altera estados de Orchestration diretamente; deve chamar casos
de uso internos.

