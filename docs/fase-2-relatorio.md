# Fase 2: modelo de dados e regras de estimativa

Status: entregue em 09/11/2026, aguardando aprovação. Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md).

## O que foi feito

| Item | Onde |
|---|---|
| As 11 regras de estimativa como funções puras, com a decisão 7 (retomada soma as partes) | `backend/modules/telemetry/domain/estimativas.py` |
| Manifesto: `execution.mode` obrigatório (`tela`, `navegador`, `segundo_plano`), `seguro_repetir`, `estado_central`, bloco `itens` e lista `etapas` | `backend/modules/catalog/domain/manifest.py`, `contracts/manifests/automation-manifest.schema.json` |
| Migration aditiva `c1d2e3f4a5b6`: `machines` (uma por Agent existente), `direct_instances`, executor genérico em `execution_attempts` e `execution_events`, `execution_items`, `step_plans`, `step_runs`, `attempt_pauses`, `estimate_snapshots`, `job_tokens`, `direct_commands` | `backend/alembic/versions/` |
| Projeção dos eventos da automação na mesma transação da gravação: itens, etapas medidas, pausas, plano de tarefas e estimativa congelada | `backend/modules/telemetry/application/use_cases/projection.py` |
| Orchestration grava itens e plano por caso de uso próprio (Telemetry não escreve nas tabelas dele) | `backend/modules/orchestration/application/use_cases/items.py` |
| Tentativa do modo direto (sem oferta, commit implícito) | `backend/modules/orchestration/application/use_cases/direct.py` |
| Token do job (hash, vence, só aquele job) e comandos do modo direto | `backend/modules/dispatch/application/use_cases/job_tokens.py` |
| **Rotas reais do modo direto**: `eventos/estado`, `eventos`, `comandos`, com auditoria de toda recusa | `backend/gateway/direct_gateway/routes.py` |
| API `GET /api/v1/executions/{id}/estimativa`: estimativa e tempo real por etapa, item, job e execução, com a base e o motivo em texto | `backend/modules/telemetry/api/routes.py` |
| API `GET /api/v1/automations/{id}/tempos?item=`: tempo por etapa de um item (execuções, típico, por tarefa, último, quando) | idem |
| Limites da ingestão alinhados ao contrato (500 eventos por lote, 64 KB por evento) | `backend/modules/telemetry/application/use_cases/events.py` |
| Testes com PostgreSQL de verdade: banco descartável, todas as migrations do zero | `backend/tests/db/` |
| Executor confiável de teste de mutação | `backend/tools/mutacao/rodar.py` |

## Testes (saída real)

```
backend> python -m pytest -q
315 passed in 41.11s

sdk\python> python -m pytest -q tests
34 passed in 21.37s

backend> python tools\mutacao\rodar.py estimativas
Linha de base: testes passam sem mutação.
Excluído: core/ReplaceBinaryOperator_BitOr_.* (| só aparece em anotações de tipo)
estimativas: 426 mutantes · KILLED: 230 · None: 187 · SURVIVED: 9
```

(`None` são os 187 excluídos.) O Agent .NET não mudou nesta fase e não foi testado de novo.

### Cenários obrigatórios desta fase (PostgreSQL, `pytest -s tests\db`)

```
cenário 6: 5066 rubricas ~500s (últimas 3 execuções do item); 9999 rubricas: rodando pela primeira vez,
           sem histórico de estimativas; job: pelo menos 805s, 3 etapa(s) sem base
cenário 7: etapas no histórico ['iniciar', 'trocar_empresa', 'rubricas', 'aviso']; txt sem base, rubricas com base
cenário 8: 30 de 50 centros feitos na 1ª tentativa; retomada estima 20 x 10s = 200s
cenário 17: 10 etapas medidas idênticas nos dois modos; estimativa do job 415s igual nos dois
regra 7: etapa de 200s com 65s de reinício -> 135s na base
regra 8: estimativa 205s igual antes e depois de 3 execuções novas
regra 6: a configuração que muda o trabalho do item mudou; o histórico anterior não vale
tempos do 5066: trocar 20s, rubricas 10s/tarefa (o 5081 levou 10x mais e não entrou)
cenário 13: token do job tsk_5647cacb… usado no job tsk_01fa2825… -> 401, auditado
cenário 15: corpo de 1,600,018 bytes -> 413; o pedido seguinte foi aceito
cenário 15: lote com 2 eventos fora do contrato -> 2 recusados, 1 gravado
```

Também cobertos: token vencido (401, auditado), sem token, token inventado, token na URL
(recusado), instância revogada (401, auditado), quarentena termina o job atual, evento acima de
64 KB, credencial direta tentando escrever na tentativa de um Agent (recusada), comando entregue
uma única vez.

## Mutantes sobreviventes: preciso que você aceite ou recuse

Os 9 são equivalentes: a troca não muda o resultado para nenhum valor que o domínio permite.

| Mutação | Por que não muda nada |
|---|---|
| `max(bruta - pausado, 0.0)` → `-1.0` | `pausado` nunca passa de `bruta`: as pausas são cortadas no intervalo da etapa |
| `max(duração, 0.0)` → `-1.0` (bruta) | Com fim antes do início, nenhuma pausa sobra e o retorno é limitado a 0 |
| `if b <= a` → `b < a` | Pausa de duração zero soma zero |
| `a > atual_fim` → `>=` | Pausas que se encostam somam o mesmo, unidas ou separadas |
| `b > atual_fim` → `>=` | Com `b == atual_fim` o fim não muda |
| `situacao != "ok"` → `< "ok"` | Todos os outros estados (`erro`, `executando`, `interrompida`) vêm antes de `ok` em ordem alfabética |
| `t > 0` → `t != 0` | Tarefas nunca são negativas (contrato com `minimum: 0`) |
| `sem_base == 0` → `<= 0` | A contagem de etapas sem base nunca é negativa |
| `amostras != 1` → `> 1` | A base sempre tem ao menos 1 amostra; com 0 não há base |

## Defeitos encontrados durante a fase

- **O cosmic-ray dava resultado falso no Windows.** Na 1ª rodada, os 433 mutantes ficaram
  "incompetentes" e o relatório dizia "0 sobreviventes". Na 2ª, marcou todos como "mortos"
  **mesmo sem mutação**: o comando de teste não achava os arquivos (caminho com espaços), e
  falhas de teste com acento quebravam a leitura da saída. Conferi aplicando mutantes à mão: 2
  de 4 sobreviviam. O `tools/mutacao/rodar.py` corrige isso e aborta se o código sem mutação não
  passar. Com o resultado real, os sobreviventes que mudavam comportamento foram mortos com
  testes novos em três rodadas, até sobrarem só os 9 equivalentes da tabela acima.
- **A retomada não seguia a decisão 7.** O código tirava da base qualquer execução com uma parte
  em erro, mesmo quando a retomada concluía a etapa. Agora conta se a última parte terminou `ok`,
  somando todas as partes, como estava documentado.
- **`is not "ok"` passaria nos testes e falharia em produção.** Com o texto vindo do banco, a
  comparação por identidade tiraria toda execução da base. Há teste com o valor montado em tempo
  de execução.
- **Ler uma execução do modo direto procurava um Agent com id nulo.** Corrigido em
  `GetExecutionDetails` e `ListExecutionSummaries`.

## Decisões que tomei e que você pode mudar

- **Tarefas previstas antes de a automação declarar:** a etapa por tarefa usa a quantidade da
  última execução concluída do **mesmo item** e diz isso (`tarefas_origem: "ultima_execucao"`).
  Quando a automação declara, a quantidade passa a ser a declarada; o ritmo por tarefa fica o
  congelado no início.
- **`tarefas_previstas` é o total da etapa no job**, contando o que tentativas anteriores já
  fizeram; `tarefas` na conclusão é o que a tentativa fez. Documentado no contrato e no SDK.
- **Corte da regra 8 = início da execução.** A estimativa é gravada em `estimate_snapshots` quando
  a tentativa e cada item começam, e nunca é reescrita.
- **Parte de etapa interrompida entra na soma** quando a retomada conclui a etapa (trabalho daquela
  execução).

## O que falta (fases seguintes)

- Os itens ainda nascem no `item.iniciado`. Na Fase 3 a fila cria os itens e grupos no
  enfileiramento, a partir do cadastro (Fase 5), e a estimativa da fila usa este modelo.
- Rota de imagens do modo direto e envio das imagens pelo Agent: Fase 4.
- Ciclo de vida da tentativa direta (passar para concluída ou falha a partir de `execucao.concluida`):
  Fase 3, junto com o despacho.
- Inscrição e desafio assinado das instâncias diretas: Fase 6.

## Riscos e limitações abertos

- **A migration roda no banco real no próximo `portal.ps1 start`** (o `start` aplica
  `alembic upgrade head`). Ela é aditiva e foi testada subindo, descendo e subindo de novo, com
  Agents existentes. O banco do portal **não** foi tocado nesta fase (continua em `b6c7d8e9f001`).
  Recomendo backup antes.
- **Manifestos sem `execution.mode` passam a ser recusados** na importação de versões novas
  (decisão 10). Versões já publicadas continuam funcionando. Automações do repositório GitHub sem
  o modo vão precisar declarar.
- `alembic check` acusa diferenças antigas (tabelas legadas e nomes de índice). Nas tabelas desta
  fase só há diferença de nome de índice, o mesmo padrão do resto do repositório.
- O histórico só começa a existir com execuções novas; nas primeiras, o correto é "Sem histórico".
- Nenhuma tela mudou nesta fase; não há capturas.
