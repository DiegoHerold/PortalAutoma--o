# Contrato de eventos da automação (`automation-events/1`)

Status: vigente desde a Fase 1 (09/11/2026). ADR-013, ADR-018.

São os eventos que a **automação** emite: etapas, itens, progresso, log, passos com
imagem, atenção, esperas e pausas. O Portal só mostra o que recebe por este contrato.
Os eventos são **os mesmos** no modo agente e no modo direto; trocar de modo é
configuração, não código.

| Arquivo | Conteúdo |
|---|---|
| `automation-event.schema.json` | Um evento (envelope e payload de cada tipo) |
| `automation-command.schema.json` | Comando do Portal para a automação |
| `event-batch.schema.json` | Lote de até 500 eventos |
| `examples/validos.json`, `examples/invalidos.json` | Um exemplo válido por tipo e os erros mais comuns |

O SDK Python (`sdk/python`) carrega uma cópia destes schemas; um teste garante que a
cópia é idêntica a esta.

## Envelope

```json
{
  "protocol_version": "automation-events/1",
  "event_id": "uuid v4",
  "sequence": 42,
  "type": "item.iniciado",
  "occurred_at": "2026-11-09T14:03:21.512Z",
  "payload": { }
}
```

- `sequence` começa em 1 em cada tentativa e é estritamente crescente. Quem recebe
  ignora sequência repetida (idempotência) e registra lacuna.
- **O contexto não vem no evento.** Execução, job, tentativa e executor são deduzidos
  pela conexão do Agent ou pelo token do job. Campo extra no envelope é recusado.
- Limites: 64 KB por evento, 500 eventos por lote. A imagem **nunca** vai no evento:
  o `passo` leva só o `imagem_id`.
- Datas sempre com fuso (RFC 3339).

## Tipos

| Tipo | Payload | Uso no Portal |
|---|---|---|
| `execucao.iniciada` | `versao_automacao?`, `sdk?` | Início da tentativa |
| `execucao.concluida` | `situacao` (`ok`, `erro`, `interrompida`, `atencao`), `resumo?` | Fim declarado pela automação |
| `etapa.iniciada` | `etapa`, `item?`, `tarefas_previstas?` | Etapa em andamento. `tarefas_previstas` é o **total** da etapa no job, contando o que tentativas anteriores já fizeram |
| `etapa.concluida` | `etapa`, `item?`, `situacao` (`ok`, `erro`, `interrompida`), `tarefas?` | `tarefas` é o que **esta tentativa** fez. Base da estimativa quando a etapa termina `ok` |
| `item.iniciado` | `item`, `rotulo?`, `grupo?`, `configuracao?` | `configuracao` leva só os atributos que mudam o trabalho; mudar um deles zera a base |
| `item.concluido` | `item`, `situacao` (`ok`, `erro`, `atencao`, `cancelado`, `ignorado`), `resumo?` | Situação do item, sem valores sensíveis |
| `progresso` | `atual`, `total`, `rotulo?`, `item?` | "centro 18 de 50" (`atual` ≤ `total`) |
| `log` | `nivel` (`debug`, `info`, `aviso`, `erro`, `critico`), `texto`, `espera?`, `item?` | `espera: true` pode ser ocultado na tela. Segredos no texto são removidos antes de gravar |
| `passo` | `rotulo`, `tipo` (`abriu`, `fechou`, `acao`, `falha`), `imagem_id?`, `item?` | Trajetória com imagem |
| `atencao` | `item`, `motivo`, `tabela?` (`colunas`, `linhas` ≤ 500), `acoes?` | O item precisa de uma pessoa; `acoes` (ex.: incluir nas ignoradas) são executadas pelo Portal |
| `espera.atualizada` | `desde`, `rotulo?`, `item?` | "N s nesta tela", sem imagem nova |
| `pausa.iniciada`, `pausa.concluida` | `motivo` (`reinicio`, `espera_externa`), `detalhe?`, `item?` | Tempo medido à parte, fora da estimativa |

Etapas e itens são opcionais. Uma automação simples emite só `execucao.iniciada`,
`log` e `execucao.concluida`.

## Comandos

Quem pede: uma pessoa com "Parar e retomar execuções", pelo botão **Parar** do Painel ou do
Acompanhar (`POST /api/v1/fila/execucoes/{id}/parar` com `modo` `apos_item` ou `agora`). No
modo direto o Portal grava o comando e a automação o recebe na próxima consulta de
`/comandos`. O SDK (0.4.0) atende sozinho:

- `parar_apos_item`: o próximo item não começa;
- `cancelar`: a automação tem 60 s para encerrar (pelo `ao_cancelar` que registrou); depois o SDK
  a interrompe.

Ver `sdk/python/README.md`. No modo agente, por enquanto só existe `cancelar`, e o Agent
encerra o processo.

Prazos do Portal, no modo direto (`backend/modules/dispatch/domain/comunicacao.py`):

- 30 s sem nenhum pedido da instância: o Painel mostra "comunicação não está ativa" e quem
  pediu é avisado;
- 2 min sem nenhum pedido: a execução é cancelada com erro, a máquina é liberada e o token do
  job é revogado;
- cancelamento sem resposta em 2 min: o Painel mostra o erro e oferece **Encerrar no Portal**
  (`POST /api/v1/fila/execucoes/{id}/encerrar`).

```json
{"protocol_version": "automation-events/1", "command_id": "cmd_1", "type": "parar_apos_item", "issued_at": "..."}
```

- `parar_apos_item`: termina o item atual e não começa outro.
- `cancelar`: interrompe o quanto antes. Sem resposta dentro do tempo de encerramento,
  o ExecutionHost encerra o processo.

Os comandos chegam pela conexão que a automação (modo direto) ou o Agent (modo agente)
abriu. Nenhuma máquina abre porta de entrada.

## Modo agente: canal local

O ExecutionHost cria um named pipe por tentativa, com acesso só do usuário que roda a
automação, e entrega o nome e um token aleatório nas variáveis `AUTOMATION_EVENTS_PIPE`
e `AUTOMATION_EVENTS_TOKEN`. Mensagens em JSON, uma por linha (UTF-8, máximo 64 KB).

| Automação → ExecutionHost | ExecutionHost → automação |
|---|---|
| `{"tipo":"ola","token":"..."}` (primeira mensagem) | `{"tipo":"ok","ultima_sequencia":N}` ou `{"tipo":"erro","motivo":"token_invalido"}` |
| `{"tipo":"evento","evento":{...}}` | `{"tipo":"ack","sequencia":N}` ou `{"tipo":"erro","motivo":"..."}` |
| `{"tipo":"ping"}` | comandos pendentes, depois `{"tipo":"pong"}` |
| | `{"tipo":"comando","comando":{...}}` (antes de qualquer resposta) |

- É de pergunta e resposta: o SDK lê e escreve na mesma thread, porque no Windows a
  leitura e a escrita síncronas no mesmo handle se bloqueiam.
- Reconexão: o `ok` traz a última sequência já repassada; o SDK descarta da fila local o
  que já chegou e reenvia o resto. Sequência repetida recebe `ack` sem ser repassada.
- O ExecutionHost faz a conferência mínima (versão, sequência, tipo) e repassa o evento
  intacto ao Agent como `automation.event`. O Agent o transporta dentro do
  `execution.event.batch` (`event_type: "automation.event"`), e o Portal valida o
  contrato inteiro.
- Imagens: o SDK grava `passos/<imagem_id>.jpg` em `AUTOMATION_ARTIFACTS_PATH` e só
  depois emite o `passo`. Ao ver o `passo`, o Agent registra o arquivo como artefato
  `passos/<imagem_id>.jpg` e o envia na hora, pelo mesmo caminho dos artefatos (URL
  temporária por HTTPS, nunca pelo WebSocket). O Portal confere a imagem e gera as três
  medidas. O coletor do fim da execução não reenvia a pasta `passos/`.

## Continuar uma execução cancelada

`POST /api/v1/fila/execucoes/{id}/continuar` cria uma execução nova só com os itens que não
deram certo (pendentes, interrompidos e com erro). Os itens `ok`, `ignorado` e `atencao` são
pulados. Cada item entregue leva `retomada`:

```json
{"chave": "5076", "rotulo": "Filial A", "grupo": "5081", "configuracao": {}, "atributos": {},
 "retomada": {"execucao_anterior": "exe_...", "situacao_anterior": "cancelado", "etapas_concluidas": ["exportar"]}}
```

`etapas_concluidas` são as etapas daquele item que terminaram `ok` na execução anterior. A
automação pode pulá-las se souber retomar dali; se não souber, faz o item inteiro de novo.
O campo só aparece em execução continuada.

## Exemplo de retomada

Primeira tentativa: `etapa.iniciada` com `tarefas_previstas: 50`, `etapa.concluida` com
`situacao: erro` e `tarefas: 30`. Retomada: `etapa.iniciada` com `tarefas_previstas: 50` de
novo; o Portal estima só as 20 que faltam.

## Modo direto: API HTTPS

Só HTTPS, TLS 1.2 ou superior, certificado validado (CA da empresa). Token do job no
cabeçalho `Authorization: Bearer <token>`, nunca na URL. O token vale só para aquele job.

| Método | Rota | Resposta |
|---|---|---|
| GET | `/api/v1/direto/jobs/{job_id}/eventos/estado` | `{"ultima_sequencia": N}` |
| POST | `/api/v1/direto/jobs/{job_id}/eventos` com `{"eventos": [...]}` | `{"ultima_sequencia": N, "recusados": [{"sequence", "motivo"}]}` |
| GET | `/api/v1/direto/jobs/{job_id}/comandos?espera=0..30` | `{"comandos": [...]}` |
| PUT | `/api/v1/direto/jobs/{job_id}/imagens/{imagem_id}` (`image/jpeg`) | `201 {"imagem_id": "..."}` |

- Evento recusado é consumido e informado em `recusados`; os válidos do mesmo lote
  são gravados.
- `401` token inválido ou de outro job · `413` acima do limite · `415` tipo de conteúdo
  errado · `422` imagem vazia ou corrompida.
- O `job_id` e o token do job chegam pela própria instância (abaixo); a automação os
  recebe prontos em `PORTAL_JOB_ID` e `PORTAL_JOB_TOKEN`.

### Instância: inscrição, sessão e próximo job

| Método | Rota | Resposta |
|---|---|---|
| POST | `/api/v1/direto/inscricao` com `{"codigo", "chave_publica" (PEM, ECDSA P-256), "nome_maquina", "versao_sdk"}` | `201 {"instancia_id", "status": "pendente"}` |
| POST | `/api/v1/direto/sessao/desafio` com `{"instancia_id"}` | `{"desafio_id", "nonce", "expira_em"}` (60 s, uso único) |
| POST | `/api/v1/direto/sessao` com `{"instancia_id", "desafio_id", "assinatura"}` | `{"token", "expira_em", "status"}` (10 min) |
| GET | `/api/v1/direto/status` | `{"instancia_id", "status", "maquina_id", "recebe_jobs"}` |
| GET | `/api/v1/direto/jobs/proximo?espera=0..30` | `{"job": null}` ou `{"job": {"job_id", "execucao_id", "tentativa", "token", "parametros", "itens"}}` |

- O código de inscrição é de uso único e vale 30 minutos; o administrador o gera na
  automação. A instância fica `pendente` até o administrador aprová-la escolhendo a
  máquina. `quarentena` abre sessão mas não recebe jobs; `revogada` não abre nada.
- A assinatura é ECDSA P-256 com SHA-256 (DER, em base64) sobre
  `portal-automacoes/direto/1|<instancia_id>|<desafio_id>|<nonce>`.
- O token da sessão vai no cabeçalho `Authorization: Bearer`. Toda recusa responde `401`
  sem dizer o motivo, que fica na auditoria.
- Enquanto a automação não mandou nenhum evento, pedir o próximo job de novo devolve o
  mesmo job com outro token (o anterior é revogado). Depois do primeiro evento, o job
  não sai de novo.
- O SDK faz tudo isso em `portal_automacoes.instancia` (`Instancia.inscrever`,
  `Instancia.carregar`, `trabalhar`). A chave privada fica cifrada pelo DPAPI do Windows,
  no escopo do usuário.
- Estado no Portal real: `eventos/estado`, `eventos`, `comandos` e `imagens` existem em
  `backend/gateway/direct_gateway/routes.py`. A imagem é conferida de novo no Portal
  (JPEG, não corrompida, não vazia, até 4 MB e 40 milhões de pixels) e guardada em três
  medidas sem metadados: miniatura (320 px), média (960 px) e cheia (até 1920 px).
  Imagem recusada fica registrada com o motivo. Repetir o envio da mesma imagem não
  duplica.
- Toda recusa de credencial (sem token, token inválido, de outro job, vencido, revogado,
  instância revogada) responde `401` e é gravada na auditoria.

## Compatibilidade

- `automation.event` foi acrescentado ao `event_type` de
  `contracts/events/execution-event.schema.json`. Agent com esta versão exige Portal com
  esta versão; um Portal antigo recusaria o evento.
- Mudança incompatível neste contrato exige `automation-events/2`.
