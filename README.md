# Portal de Automacoes

Portal de Automacoes e o control plane do ecossistema de automacoes. Ele
define o que pode ser executado, publica versoes imutaveis, cria execucoes,
seleciona Agents candidatos, registra eventos e mantem o estado oficial.

O Automation Agent e o execution plane. Ele roda em maquinas de execucao,
observa recursos locais, valida ofertas, prepara runtimes e pacotes, executa
automacoes, gera eventos e envia artefatos.

## Arquitetura oficial

A arquitetura vigente esta em `docs/architecture.md`. As decisoes principais
estao em `docs/adrs/` e os contratos versionados ficam em `contracts/`.

Principios centrais:

- Portal decide o que precisa ser executado.
- Portal escolhe Agents candidatos.
- Agent faz a validacao final de admissao e pode rejeitar uma oferta.
- PostgreSQL e a fonte oficial de estados persistentes.
- WebSocket, Redis, Celery e mensageria sao meios de transporte ou execucao
  interna, nao fontes de verdade.
- Arquivos grandes trafegam por HTTPS/S3, nao pelo WebSocket.

## Stack atual

- `backend/`: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery,
  storage local/S3 e gateway de Agent.
- `frontend/`: Next.js, TypeScript e Tailwind para a interface operacional.
- `infra/`: configuracao de monitoramento.
- `scripts/portal.ps1`: sobe e derruba o Portal nativamente no Windows.
- `docs/`: contexto arquitetural, ciclos de vida, migracao e ADRs.
- `contracts/`: schemas versionados de protocolo, mensagens, eventos,
  manifests, capabilities e codigos de erro.

## Estado de migracao

O codigo atual ainda usa os nomes legados `Worker`, `Job` e `Execution` em
varios pontos. Eles permanecem por compatibilidade enquanto a migracao gradual
introduz `Agent`, `AgentInstance`, `Execution`, `TaskExecution`,
`ExecutionAttempt` e `ExecutionOffer`.

Nao remova dados nem endpoints legados sem seguir `docs/migration.md`.

## Primeiro uso

1. Prepare a maquina com `.\scripts\portal.ps1 setup` (requisitos em
   `docs/deployment.md`).
2. Suba o Portal com `.\scripts\portal.ps1 start`.
3. Acesse o frontend em `http://localhost:3000`.
4. Entre com `admin@portal.local` / `admin123`.

## Proxima fatia vertical

A proxima implementacao deve provar o caminho:

```text
AutomationVersion publicada
-> Agent registrado
-> Heartbeat recebido
-> Execucao criada
-> Oferta enviada
-> Agent aceita
-> Portal envia commit
-> Agent executa
-> Eventos chegam
-> Execucao concluida
-> Artefato disponivel
```
