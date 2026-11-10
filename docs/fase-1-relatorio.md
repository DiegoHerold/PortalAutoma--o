# Fase 1: contrato de telemetria, SDK, canal no Agent e simuladores

Status: entregue em 09/11/2026, aguardando aprovação. Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md).

## O que foi feito

| Item | Onde |
|---|---|
| 3 testes quebrados corrigidos (um era violação real de fronteira no gateway) | `backend/gateway/agent_gateway/endpoint.py`, `backend/modules/dispatch/...` |
| ADR-018 (modo direto), ADR-019 (máquina), ADR-020 (redesenho); ADR-017 marcado como substituído; `AGENTS.md` atualizado | `docs/adrs/`, `AGENTS.md` |
| Contrato `automation-events/1`: 13 tipos de evento, comandos, lote, exemplos válidos e inválidos | `contracts/automation-events/v1/` |
| `automation.event` no `execution.event.batch` do protocolo Portal–Agent | `contracts/events/execution-event.schema.json` |
| Portal aceita e valida `automation.event` pelo schema (64 KB, regras extras), remove segredos do texto do log | `backend/modules/telemetry/infrastructure/adapters/automation_events.py` |
| Canal local no ExecutionHost: named pipe por tentativa, só do usuário, token, ACK, idempotência, reconexão, `ping`, comandos, limite de 64 KB | `automation-agent/src/Agent.ExecutionHost/Protocol/AutomationEventsServer.cs` |
| `automation.event` repassado intacto nos caminhos de segundo plano e de tela (SessionRunner) | `Agent.Application`, `Agent.Protocol`, `Agent.SessionRunner` |
| Cancelamento por tempo limite agora pede `cancelar` à automação e espera o encerramento gracioso antes de matar | `Agent.ExecutionHost/Program.cs` |
| Escritas no pipe do Agent serializadas (stdout, stderr, métricas e eventos escreviam ao mesmo tempo) | `Agent.ExecutionHost/Protocol/PipeClient.cs` |
| SDK Python com os dois transportes, fila em disco, imagens conferidas, comandos | `sdk/python/portal_automacoes/` |
| Agent simulado (Agent Service em Python + ExecutionHost.exe real), Portal simulado (HTTPS, CA própria), automação de exemplo | `sdk/python/simuladores/` |
| HTTPS no uvicorn: `PORTAL_TLS_CERT` e `PORTAL_TLS_KEY`, TLS 1.2+, cifras AEAD, health check validado | `scripts/portal.ps1`, `backend/.env.example`, `docs/deployment.md` |

## Defeitos encontrados durante a fase

- **O uvicorn não negociava TLS 1.2** com o padrão `--ssl-ciphers TLSv1` (só cifras SHA-1).
  Um Agent em Windows sem TLS 1.3 não conectaria. Corrigido com cifras AEAD explícitas.
- **O SDK travava** se o Agent respondesse `erro` em vez de `pong`, ou se ficasse mudo.
  Agora o erro vira exceção tratada e toda leitura tem tempo limite de 30 s.
- **Escritas concorrentes no pipe do Agent** no ExecutionHost, já existentes antes desta
  fase. Corrigido com um lock.
- **O comando de cancelamento travava o ExecutionHost.** O canal de eventos foi criado com
  buffer zero, e cada escrita esperava a automação ler. No encerramento por tempo limite,
  o ExecutionHost ficaria parado no envio do `cancelar` e nunca encerraria o processo.
  Apareceu como queda do host de testes do .NET. Corrigido com buffer de 128 KB e prazo de
  5 s para enviar um comando (passado o prazo, ele volta para a fila). Há teste de
  regressão (`Comando_ComAutomacaoQueNaoLeOPipe_NaoTravaQuemEnvia`).

## Cenários obrigatórios cobertos nesta fase

| Cenário | Situação |
|---|---|
| 13. Token de job de outro job: recusado | ✅ no Portal simulado (`test_token_de_outro_job_e_recusado`). No Portal real, Fase 2 |
| 15. Payload acima do limite ou fora do schema: recusado sem derrubar | ✅ Portal real (`test_evento_acima_do_limite...`, `test_exemplo_invalido...`), ExecutionHost (`LinhaAcimaDoLimite...`) e SDK |
| 17. Mesma automação, modo direto e modo agente: mesmos eventos | ✅ eventos idênticos (`test_cenario_17_...`). Mesmo histórico e mesma estimativa dependem da Fase 2 |
| Demais | Fases 2 a 6 |

## O que falta (fases seguintes)

- Rotas reais do modo direto no Portal (`/api/v1/direto/...`) e executor genérico: Fase 2.
- Envio das imagens do modo agente ao Portal (o SDK já grava em `artifacts/passos`): Fase 4.
- Comando `parar_apos_item` do Portal até o ExecutionHost (o canal já entrega; falta o
  caminho Portal → Agent → ExecutionHost): Fase 4.
- Inscrição, desafio assinado, DPAPI e pedido de jobs pela instância direta: Fase 6.

## Riscos e limitações abertos

- **O frontend continua em HTTP.** O Next.js standalone não termina TLS. Opções: um proxy
  reverso só para o frontend, ou servir o build estático pela própria API. Precisa de
  decisão antes da Fase 3.
- **TLS é opcional no `portal.ps1`** para não derrubar a instalação atual. Sem as
  variáveis, a API sobe em HTTP com aviso. Tornar obrigatório é uma decisão sua.
- **O Agent .NET exige Portal desta versão**: um Portal antigo recusaria `automation.event`.
- O teste do modo agente exige o ExecutionHost compilado (`dotnet build`); sem ele, é pulado
  com o motivo.
- O cenário 17 compara os eventos; ainda não compara histórico nem estimativa.
- A sessão interativa (SessionRunner) recebeu o mapeamento de `automation.event`, mas não
  foi exercitada de ponta a ponta numa sessão de tela real nesta fase.
- Nenhuma tela mudou nesta fase; não há capturas.
