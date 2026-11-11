# Fase 3: fila, despacho, trava de tela e a tela Fila

Status: aprovada em 10/11/2026 (mutantes equivalentes aceitos). Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md).

## O que foi feito

| Item | Onde |
|---|---|
| Regras da fila como funções puras: ordem (prioridade, posição manual, chegada do lote, mais longo primeiro dentro do lote), previsão por máquina, próximo job da máquina, vagas (tela limitada a 1), agrupamento por matriz, duplicata, "pode repetir sozinho" | `backend/modules/dispatch/domain/fila.py` |
| A previsão guarda **qual job** segura a vaga sem horário, para o motivo nomear a automação e os itens | idem (`Previsao.aguardando`) |
| Migration aditiva `d2e3f4a5b6c7`: campos de fila em `task_executions`, índice único de duplicata só para jobs ativos, trava por máquina em `resource_locks`, capacidade por tipo em `machines`, último sinal da instância direta | `backend/alembic/versions/d2e3f4a5b6c7_fase3_fila_e_trava_de_tela.py` |
| Pedir execução: um job por grupo, pedido igual aponta para o job existente (também com 2 pedidos no mesmo instante) | `backend/modules/orchestration/application/use_cases/queue.py` |
| Despacho: Agent recebe o job só para ele (oferta e commit continuam no fluxo existente); modo direto toma a trava de tela da máquina pelo índice único | `backend/modules/dispatch/application/use_cases/queue.py` |
| Job perdido nunca volta sozinho: fica `lost`, a máquina fica travada até a decisão; `continuar` (mesma máquina, salvo estado central) ou `recomecar` (do zero) | idem + `resilience.py` |
| Fim declarado no modo direto conclui a tentativa e libera a máquina | `projection.py`, `ConcluirTentativaDireta` |
| API `/api/v1/fila`: ver, pedir, prioridade, cancelar, decidir perdido, despachar (admin) | `backend/modules/dispatch/api/fila.py` |
| Celery: despacho a cada 5 s (marca perdidos e entrega) | `backend/workers/` |
| **Visibilidade**: só aparecem jobs de automações que o usuário pode ver; quem não é admin vê a máquina ocupada e o tempo restante, mas não qual job a ocupa; motivo que cita automação alheia vira texto genérico | `backend/modules/dispatch/api/fila.py` |
| Identidade Biason em todo o portal (tokens claro e escuro, Barlow e Barlow Condensed, menu com logo, eyebrow, faixa noite) | `frontend/src/app/globals.css`, `layout.tsx`, `tailwind.config.ts`, `components/layout/` |
| Tela **Fila** | `frontend/src/app/(dashboard)/fila/`, `frontend/src/components/fila/fila-manager.tsx`, `frontend/src/lib/fila.ts` |
| Testes de tela com Playwright | `frontend/e2e/fila.spec.ts`, `frontend/playwright.config.ts` |
| Documentação | `docs/design-system.md` (reescrito), `docs/frontend-integration.md` (rotas da Fila) |

## Testes (saída real)

```
backend  (pytest, suíte inteira)            383 passed in 55.88s
backend  tests/db/test_fase3_fila.py +
         modules/dispatch/tests/test_fila.py 68 passed in 13.13s
sdk/python                                   34 passed in 21.78s
frontend tsc --noEmit                        sem erros
frontend npx playwright test                 10 passed (30.7s)
```

### Cenários desta fase (PostgreSQL, `pytest -s tests/db/test_fase3_fila.py`)

```
cenário 4: 2º pedido igual -> job tsk_cfbf3d89… existente; outra competência -> job novo
cenário 4 (simultâneo): 2 pedidos no mesmo instante -> 1 job
cenário 3: matriz 5081 + filiais 5076 e 5075 num job só, numa máquina só (2 job(s) entregues)
cenário 1 (fila real, estimativas do histórico):
  1. empresa 8050 ~50 min -> A-1, início 11:11, término 12:01
  2. empresa 8040 ~40 min -> B-1, início 11:11, término 11:51
  3. empresa 8030 ~30 min -> B-1, início 11:51, término 12:21
  4. empresa 8020 ~20 min -> A-1, início 12:01, término 12:21
  5. empresa 8010 ~10 min -> A-1, início 12:21, término 12:31
cenário 5: 2 travas de tela pedidas no mesmo instante na mesma máquina -> 1 concedida
cenário 16: máquina com Agent e instância direta -> 1 job de tela por vez; o seguinte espera
  (início previsto: sem previsão; motivos: ['aguardando o término de Integração Contábil ebfcbb2d (9101),
  que está sem previsão', 'etapas Iniciar, Trocar empresa, Rubricas e mais 2 (item 9102) rodando pela
  primeira vez, sem histórico de estimativas'])
cenário 2: instância sem sinal -> job perdido; 3 ciclos depois continua perdido;
  'continuar' devolve para a mesma máquina (mch_f32d6bbb5657)
cenário 14: instância revogada e em quarentena -> nenhum job entregue
fila: sem máquina -> motivo 'nenhuma máquina tem esta automação'; prioridade 9 passa à frente;
  cancelado sai da fila
motivos para quem vê as duas automações: ['aguardando o término de Integração Contábil 57f5d19d (9701),
  que está sem previsão', 'etapas Iniciar, Trocar empresa, Rubricas e mais 2 (item 9702) ...']
motivos para quem só vê a segunda: ['aguardando o término de um job que não tem previsão',
  'etapas Iniciar, Trocar empresa, Rubricas e mais 2 (item 9702) ...']
15 passed in 29.99s
```

### Testes de tela (Playwright)

A API é simulada só dentro do teste. Cada teste falha se aparecer erro no console.

```
ok  1 fila com jobs, máquinas e perdido — desktop, tema claro
ok  2 fila com jobs, máquinas e perdido — celular, tema claro
ok  3 fila com jobs, máquinas e perdido — desktop, tema escuro
ok  4 fila com jobs, máquinas e perdido — celular, tema escuro
ok  5 Sem previsão aparece sempre com o motivo
ok  6 cancelar mostra o efeito antes e só então chama a API
ok  7 subir prioridade manda o novo valor
ok  8 job perdido: continuar explica que só volta na mesma máquina
ok  9 fila vazia e sem máquinas explica o que falta
ok 10 o painel inicial também ganhou a identidade Biason
10 passed (30.7s)
```

## Telas

Os dados dos prints são do teste: não estão na aplicação.

| Tela | Arquivo |
|---|---|
| Fila, desktop, claro | [fila-desktop-claro.png](fase-3-telas/fila-desktop-claro.png) |
| Fila, desktop, escuro | [fila-desktop-escuro.png](fase-3-telas/fila-desktop-escuro.png) |
| Fila, celular, claro | [fila-celular-claro.png](fase-3-telas/fila-celular-claro.png) |
| Fila, celular, escuro | [fila-celular-escuro.png](fase-3-telas/fila-celular-escuro.png) |
| Confirmar "Continuar" de job perdido | [fila-confirmar-continuar.png](fase-3-telas/fila-confirmar-continuar.png) |
| Confirmar cancelamento | [fila-confirmar-cancelamento.png](fase-3-telas/fila-confirmar-cancelamento.png) |
| Fila vazia, sem máquinas | [fila-vazia.png](fase-3-telas/fila-vazia.png) |
| Painel inicial com a nova identidade (só tokens; o redesenho dele é de outra fase) | [dashboard-claro.png](fase-3-telas/dashboard-claro.png) |

## Mutantes sobreviventes: preciso que você aceite ou recuse

`python tools/mutacao/rodar.py fila` (cosmic-ray, domínio da fila):

```
Linha de base: testes passam sem mutação.
Excluído: core/ReplaceBinaryOperator_BitOr_.* (| só aparece em anotações de tipo)
fila: 380 mutantes · KILLED: 218 · None: 154 · SURVIVED: 8
```

(`None` = mutantes descartados pelo filtro, como o `|` das anotações.) Os 8 que
sobrevivem não mudam o comportamento com os valores possíveis. Os tipos de vaga
são só `interactive` (tela), `browser` e `background`, validados pelo manifesto.

| Mutante | Por que não muda nada |
|---|---|
| `pool != TELA` → `pool < TELA` (pode repetir sozinho) | `browser` e `background` vêm antes de `interactive` em ordem alfabética: para os três tipos o resultado é igual |
| `if pool == TELA` → `>=` (2 lugares: limite de 1 por máquina) | nenhum tipo vem depois de `interactive` em ordem alfabética |
| `-prioridade` → `~prioridade` | `~x` é `-x - 1`: a ordem não muda |
| `posicao_manual ... else 0` → `else 1` e `else -1` | a chave anterior (`posicao_manual is None`) já separa quem não tem posição; entre esses o valor é o mesmo para todos |
| `-(estimativa_s or 0.0)` → `or -1.0` | idem: a chave anterior (`estimativa_s is None`) já separa quem não tem estimativa |
| `range(max(capacidade, 0))` → `max(capacidade, -1)` | `range` de número negativo já é vazio |

Proposta: aceitar os 8 como equivalentes. O código novo desta rodada
(`aguardando`, quem segura a fila) teve todos os mutantes mortos.

## Defeitos encontrados durante a fase

- A trava de tela apontava para uma tentativa que ainda não existia (chave estrangeira). A tentativa agora é criada antes, dentro de um savepoint, que é desfeito se a trava falhar.
- O caminho do Agent chamava `replace()` num registro do ORM. Agora usa o DTO.
- `GET /fila` mandava `rodando[].job_id` para qualquer usuário, inclusive de automações que ele não pode ver. Corrigido e coberto por teste.
- `etapas_sem_base` era um número, e a tela esperava uma lista. Agora é a lista dos nomes das etapas, como no manifesto.
- O motivo "aguardando término" não dizia de quem. Agora nomeia a automação e os itens (decisão 2 da Fase 0).
- **Defeito causado por mim:** a primeira rodada do Playwright subiu `next dev` em `frontend/`, e o `next dev` limpou `frontend/.next`, inclusive `.next/standalone`, de onde o portal roda. Ver "Ação sua" abaixo. Para não repetir, o teste agora usa `NEXT_DIST_DIR=.next-e2e` e `tsconfig.e2e.json`.

## Reinício do portal (feito em 10/11/2026, com sua autorização)

- A primeira rodada do Playwright apagou `.next/standalone` (ver defeitos acima).
  Restaurei com o build do HEAD e, depois da aprovação, gerei o build da Fase 3.
- O build travava enquanto o `server.js` antigo estava de pé: no Windows, a pasta
  de trabalho do processo não pode ser removida e o Next fica tentando limpar o
  `.next`. Com o portal parado, o build passou (`/fila` incluída).
- `portal.ps1 start`: o banco real **já estava** em `d2e3f4a5b6c7` antes do
  reinício (conferido no backup feito antes, `antes-fase3-20261110-082007.dump`).
  A afirmação anterior deste relatório, de que ele estava em `b6c7d8e9f001`, estava
  errada. Não havia migration a aplicar.
- Depois do reinício: JS, CSS e logo respondem 200; `GET /api/v1/fila` responde
  401 sem login; `/health` responde 200.

## Decisões que tomei e que você pode mudar

- "Fila" fica no menu em **Visão geral**, logo abaixo do Dashboard, para quem tem `execution.read` ou `automation.read`.
- A tela relê a fila a cada **5 s**. O tempo real é da Fase 4.
- Prioridade sobe e desce de 1 em 1 pela própria linha. A posição manual existe na API, mas ainda não tem controle na tela.
- O painel "Por que espera" monta a explicação na tela a partir dos dados da API (posição, prioridade, máquina prevista, motivos), sem chamada extra.
- Pedir execução (`POST /fila/execucoes`) ainda não tem tela: fica para quando a automação ganhar a tela própria.

## O que falta (fases seguintes)

- Fase 4: tempo real (eventos de passo, imagem por passo, "N s nesta tela", logs ao vivo) e troca da releitura de 5 s.
- Fase 5: telas da automação e Central de telas do admin.
- Fase 6: entrega do job e do token ao modo direto (hoje o despacho cria a tentativa e a trava, mas a instância ainda não recebe o job por rota própria).

## Riscos e limitações abertos

- **Credencial na URL (já existia):** o tempo real legado manda o JWT na query string em `WS /ws/executions` (`frontend/src/hooks/use-realtime.ts`) e em `GET /executions/{id}/stream` (`backend/modules/telemetry/api/routes.py`). Isso viola "credenciais nunca aparecem em URL". Proponho corrigir na Fase 4, que reescreve o tempo real.
- **`next@15.4.6`** acusa vulnerabilidade no `npm ci` (CVE-2025-66478). Não atualizei: está fora do escopo da fase e muda a base do frontend. Recomendo tratar à parte.
- A previsão trata todo Agent habilitado como capaz de rodar qualquer automação. Uma incompatibilidade só aparece na oferta, quando o Agent recusa.
- Fluxos (várias automações encadeadas) ainda não têm caminho crítico na estimativa.
- O frontend continua em HTTP. A decisão de HTTPS do frontend segue aberta.
- O painel inicial e as demais telas pegaram só os tokens novos. Textos como "Workers" continuam até cada tela ser refeita na sua fase.
- O portal **não** está pronto para produção.
