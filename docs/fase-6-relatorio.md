# Fase 6: notificações, retenção por automação e telas administrativas no visual novo

Status: entregue, aguardando sua aprovação. Plano em
[fase-0-diagnostico-orquestracao.md](fase-0-diagnostico-orquestracao.md) (seção 10).

A inscrição e a revogação do modo direto, que o plano punha nesta fase, já tinham sido
antecipadas e entregues na Fase 4. A remoção de segredos do log também já estava pronta desde
a Fase 4.

## Suas decisões (10/11/2026)

| Pergunta | Resposta | Efeito |
|---|---|---|
| Prazo padrão de imagens e logs | **Sem padrão** | Nada é apagado até alguém definir o prazo de uma automação |
| Servidor de e-mail | **Microsoft Graph, mas sem enviar ainda** | O envio pelo Graph existe e fica **desligado**. Os avisos aparecem no sino do portal |
| Quem recebe "máquina offline" e "fila parada" | **Só administradores e gestores** | Para os demais, a API responde 422 e a tela nem mostra a opção |

## O que foi feito

### Notificações

| Item | Onde |
|---|---|
| Regras puras para os cinco tipos (erro, item aguardando uma pessoa, máquina offline, fila parada e término). Uma **ocorrência agregada**: a execução que falha é uma ocorrência só (erro e término), e **cada endereço recebe no máximo um aviso** por ocorrência, mesmo com duas pessoas no mesmo e-mail ou dois tipos ligados | `backend/modules/telemetry/domain/notificacoes.py` |
| Quem recebe: erro, atenção e término só quem pode ver a automação (concessão `ver_execucoes` ou `central_de_telas`); máquina e fila só gestores; fila parada só quem escolheu aquele tempo | idem |
| Nada repete: a chave da ocorrência é única no banco (`uq_notifications_chave`) e o aviso é único por endereço (`uq_notification_deliveries_endereco`). Detectar de novo não cria nada | `alembic/versions/b6c7d8e9f0a1_...`, `infrastructure/repositories/sqlalchemy_notificacoes.py` |
| Nada antigo despejado: só o que aconteceu nas últimas 24 h vira ocorrência. Toda ocorrência é gravada, mesmo sem destinatário, para quem liga um tipo depois não receber o passado | `application/use_cases/notificacoes.py` |
| Detecção a cada 30 s e envio a cada 60 s (Celery Beat). E-mail que não saiu em 6 h expira; 5 falhas marcam "falhou" | `workers/tasks/notificacoes_tasks.py`, `workers/celery_app.py` |
| **Envio pelo Microsoft Graph** (credencial de aplicativo, `sendMail`), desligado por padrão. HTTPS com certificado sempre validado e sem opção de desligar. O segredo fica só no `.env` e nunca aparece em URL, log, mensagem de erro ou `repr` | `modules/telemetry/infrastructure/email_graph.py`, `backend/.env.example` |
| Rotas: `GET /notificacoes`, `POST /notificacoes/lidas`, `GET` e `PUT /notificacoes/preferencias` | `modules/telemetry/api/notificacoes.py` |
| **Sino de avisos** no topo: contagem por ler, lista, marcar como lidos e atalho para as preferências | `frontend/src/components/layout/sino-de-avisos.tsx` |
| **Configurações > Notificações**: cada pessoa liga o que quer (nada vem ligado). Fila parada pede o tempo (5 a 1440 min). A tela diz que o e-mail ainda está desligado | `frontend/src/components/settings/notificacoes.tsx` |

### Retenção por automação

| Item | Onde |
|---|---|
| Prazo em dias (1 a 3650) para **imagens** e para **logs**, por automação. Sem prazo, nada sai | `modules/governance/domain/retencao_por_automacao.py`, `application/retencao.py`, `api/retencao.py` |
| Limpeza a cada hora, em lotes. **Imagens**: os bytes das três medidas saem pelo Storage (novo caso de uso `ApagarObjeto`, objeto marcado `deleted`). A linha da imagem fica com `apagada_em`, e a API responde **410**. **Logs**: só as linhas de log; etapas, progresso, passos e o histórico de tempos (`step_runs`) ficam, então as estimativas não mudam | `modules/telemetry/infrastructure/repositories/sqlalchemy_retencao.py`, `modules/storage/application/use_cases/objetos.py` |
| Auditoria: definir o prazo (com o valor anterior) e cada limpeza que apagou algo (com as contagens e o corte) | `application/retencao.py` |
| Tela **Retenção**: lista das automações com os prazos; editar pede confirmação quando o novo prazo apaga mais ("apagado de vez, não tem volta"). As políticas antigas por tipo de registro continuam, com o aviso de que ainda não apagam nada | `frontend/src/components/governance/retencao-por-automacao.tsx`, `app/(dashboard)/governance/retention/page.tsx` |
| Acompanhar e Painel mostram "Imagem apagada pela retenção em dd/mm/aaaa" em vez de "indisponível" | `frontend/src/lib/acompanhar.ts` (`semImagem`) |

### Telas administrativas no visual novo

- **Textos com acento** em Segredos, Contas de serviço, Organizações, Times, Limites,
  Retenção, Auditoria, Runtimes, Usuários, Webhooks e outras (26 arquivos). Um script mexeu
  só em textos visíveis, nunca em chaves de API. O que ele não decide sozinho ("e" ou "é",
  textos misturados com código) corrigi à mão.
- **Filtros escondidos**: só a busca fica à mostra e o resto fica atrás de "Filtros", em
  Segredos, Contas de serviço, Organizações, Times, Limites e Retenção
  (`components/shared/filtros-escondidos.tsx`).
- Cartões com canto maior e títulos em Barlow Condensed (`Card`, `SectionCard`,
  `EmptyState`).
- O rótulo acima do título agora é a categoria do menu (Segurança, Pessoas e acesso,
  Governança...).

### Seus pedidos de visual nesta rodada

| Pedido | O que mudou |
|---|---|
| "Tire o Portal de Automações, deixe só o logo" | Topo do menu só com o logo Biason |
| "Reorganizar a ordem clicando e arrastando no menu" | Arraste um item para cima ou para baixo dentro da categoria, ou arraste o nome da categoria. Pelo teclado: Alt+↑/↓. Fica gravado no navegador; "Restaurar padrão" (Configurações) volta tudo |

## Testes (saída real)

```
backend   (pytest, suíte inteira)                    554 passed in 124.34s
frontend  tsc --noEmit                               sem erros
frontend  npx playwright test                        40 passed (2.4m)
```

### Cenários no PostgreSQL (`pytest -s tests/db/test_fase6_notificacoes_retencao.py`)

```
notificações: 1ª detecção {'ocorrencias': 3, 'avisos': 3}, 2ª {'ocorrencias': 0, 'avisos': 0};
  fim -> gestor e operador (sem_acesso não); offline -> só gestor; envio desligado mantém pendente;
  com carteiro {'ligado': 1, 'enviados': 3, 'expirados': 0, 'falhas': 0}
retenção: sem prazo nada sai; com 30 dias -> 1 imagem (3 medidas apagadas no Storage, 410) e
  2 linhas de log; etapa fica; auditoria ['retencao.definida', 'retencao.aplicada']
2 passed
```

O "carteiro" desse teste é um dublê que fica só no teste, no lugar do Graph. O envio pelo
Graph tem testes próprios com um transporte HTTP de teste, sem rede. Eles conferem o pedido
de token e o `sendMail`, o reaproveitamento do token, a recusa sem expor o segredo e a falha
de rede (`modules/telemetry/tests/test_envio_email.py`).

### Testes de tela

```
ok sino: avisos por ler, lista e marcar como lidos
ok notificações: cada pessoa escolhe; fila parada pede o tempo; e-mail desligado é dito
ok notificações: quem não é gestor não vê máquina offline nem fila parada
ok retenção por automação: sem prazo nada sai; encurtar avisa que apaga (claro e escuro)
ok telas administrativas no visual novo: papéis, segredos, contas de serviço, times, limites
ok resposta fora do formato nas notificações não derruba as Configurações
ok menu lateral: arrastar muda a ordem e fica gravada; só o logo no topo
```

## Telas

| Tela | Arquivo |
|---|---|
| Sino de avisos | [sino-de-avisos.png](fase-6-telas/sino-de-avisos.png) |
| Configurações > Notificações | [notificacoes-preferencias.png](fase-6-telas/notificacoes-preferencias.png) |
| Retenção, claro e escuro | [claro](fase-6-telas/retencao-claro.png), [escuro](fase-6-telas/retencao-escuro.png), [confirmar](fase-6-telas/retencao-confirmar.png) |
| Telas administrativas | [papéis](fase-6-telas/admin-papeis.png), [segredos](fase-6-telas/admin-segredos.png), [contas de serviço](fase-6-telas/admin-contas-de-servico.png), [times](fase-6-telas/admin-times.png), [limites](fase-6-telas/admin-limites.png) |
| Menu reordenado | [menu-reordenado.png](fase-5-telas/menu-reordenado.png) |

## Mutantes sobreviventes: preciso que você aceite ou recuse

```
retencao:     104 mutantes · KILLED: 38 · None: 66 · sem sobreviventes
notificacoes: 449 mutantes · KILLED: 238 · None: 209 · SURVIVED: 2
```

"None" são os mutantes de `|` em anotação de tipo, excluídos como nas fases anteriores.

| Mutante | Por que não muda nada |
|---|---|
| `ultimo_inicio > desde` → `>=` | quando os dois são iguais, `desde` recebe o mesmo valor |
| `tipos - {FILA_PARADA}` → `tipos ^ {FILA_PARADA}` | a linha só roda quando `FILA_PARADA` está em `tipos`; aí tirar e alternar dão o mesmo |

**Um problema que achei e corrigi:** na primeira rodada, um mutante estourou o tempo e o
`cosmic-ray` não devolveu o arquivo original. `notificacoes.py` ficou com `break` no lugar de
`continue`. Um teste que antes passava acusou, e eu restaurei a linha e conferi o arquivo
inteiro. Agora o `tools/mutacao/rodar.py` guarda uma cópia antes e devolve o original se
algo ficar para trás. Conferi também os alvos das fases anteriores, que estão iguais ao
commit.

**Outro problema que achei e corrigi (vinha desde a Fase 4):** os testes gravavam as
imagens sintéticas na pasta **real** de armazenamento do portal
(`%LOCALAPPDATA%\PortalAutomacoes\packages`), e não na pasta temporária. A causa: um teste
zera o cache das configurações, e a instância nova voltava a ler o `.env` real. Nenhum
registro foi para o banco real, só arquivos. Confirmei, só lendo o banco real, que os 232
arquivos (222 imagens e 10 `img_agente.jpg`) não pertencem a nenhuma execução real. Eu os
tirei da pasta do portal e os guardei fora dela, então dá para devolver. Agora um
`backend/conftest.py` fixa a pasta temporária para todos os testes antes de tudo. Rodei a
suíte inteira de novo e a pasta real não ganhou nenhum arquivo (232 antes, 232 depois;
agora 0).

## Decisões que tomei e que você pode mudar

- **Sino no portal**: como o e-mail ainda não sai, os avisos ficam visíveis no sino. Quando
  o envio for ligado, o mesmo aviso também vai por e-mail.
- **"Erro" inclui** falha, tempo esgotado e "parte dos itens falhou". Cancelada conta só
  como término.
- **Fila parada** = há job esperando e nenhum job começou há mais que o tempo escolhido,
  contando do mais recente entre o job mais antigo da fila e o último início. Um job de tela
  longo rodando sozinho também conta como fila parada se houver outro esperando.
- **Máquina offline**: um aviso por queda (o último sinal identifica a queda). Máquina que
  nunca deu sinal, ou que caiu há mais de um dia, não gera aviso.
- **Logs na retenção** = só as linhas de log. Etapas, passos e progresso ficam (não têm
  imagem e alimentam a linha do tempo da execução).
- E-mail em texto simples, sem imagem e sem trecho de log (LGPD), com o link para o portal.

## Para ligar o e-mail (quando você quiser)

1. Registrar um aplicativo no Entra ID com a permissão de aplicativo **Mail.Send**. O ideal
   é restringir a uma caixa só, a do remetente, com uma *application access policy*.
2. No `backend/.env`: `NOTIFICACOES_EMAIL_LIGADO=true`, `GRAPH_TENANT_ID`,
   `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` e `GRAPH_REMETENTE`.
3. Reiniciar o portal. As Configurações passam a dizer que o e-mail está ligado.

## O que falta

- **Ações a partir da atenção** (ex.: "Ignorar rubrica" grava no cadastro do item): ficou
  para depois, como na Fase 5.
- Ligar a Integração Contábil (certificado assinado e cadastro), quando você pedir.
- Telas administrativas: as mudanças foram acentos, filtros, cartões e rótulos. Usuários,
  Auditoria, Agendamentos e Webhooks mantêm o mesmo leiaute de antes (só ganharam essas
  correções). Um redesenho completo dessas telas seria outra rodada.

## Riscos e limitações abertos

- O e-mail pelo Graph foi testado só com um transporte de teste. O primeiro envio real
  precisa da sua configuração e de um teste com uma caixa de verdade.
- A ordem e os itens do menu ficam no navegador de cada pessoa, não na conta.
- A detecção relê as últimas 24 h a cada 30 s. Isso é bom para centenas de execuções por
  dia; para muito mais, valeria um cursor.
- A retenção apaga em lotes (500 imagens e 5000 linhas de log por automação por hora).
  Uma automação com muito acúmulo leva algumas horas para ficar em dia.
- As políticas antigas por tipo de registro (tela Retenção, parte de baixo) seguem sem
  efeito, como já eram.
- O portal **não** está pronto para produção.
