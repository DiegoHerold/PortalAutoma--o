# Telemetry

Ownership: eventos, logs, progresso, metricas, sequencias, deduplicacao, ACK,
deteccao de lacunas, timeline e realtime.

Legado a migrar:

- `app/models/log.py`
- `app/services/realtime_service.py`
- `app/services/websocket_broadcaster.py`
- `app/api/v1/endpoints/realtime.py`

Telemetry nao altera estados de Orchestration diretamente; deve chamar casos
de uso internos.

