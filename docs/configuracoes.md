# Configurações do sistema: limites e limpeza automática

Status: vigente (13/11/2026).

Tudo o que o Portal configura sozinho fica num catálogo só:
[`backend/modules/governance/domain/configuracoes.py`](../backend/modules/governance/domain/configuracoes.py).
Cada entrada tem nome, descrição, valor padrão, faixa aceita e onde vale. O banco guarda só o
que alguém mudou. Sem linha gravada, vale o padrão do catálogo, então tudo já funciona na
instalação.

Telas: **Governança > Limites** (`/governance/limits`) e **Governança > Retenção**
(`/governance/retention`). Toda mudança e toda limpeza que apagou algo entram na auditoria.

## Onde achar cada coisa

| O quê | Onde |
|---|---|
| Lista de limites e regras (nome, padrão, faixa) | `governance/domain/configuracoes.py` |
| Leitura de um limite por outro contexto | `governance/infrastructure/limites.py` (`ler_limite(db, chave)`) |
| Quem apaga cada regra de limpeza | `governance/infrastructure/adapters/limpeza.py` (`LIMPADORES`) |
| As funções que apagam (cada contexto, só as suas tabelas) | `<contexto>/infrastructure/limpeza.py` |
| Casos de uso (listar, mudar, aplicar) | `governance/application/configuracoes.py` |
| API | `governance/api/configuracoes.py` |
| Tarefa periódica | `workers/tasks/housekeeping_tasks.py` (`aplicar_limpeza_do_sistema`, a cada 30 min) |
| Telas | `frontend/src/components/governance/limites-do-sistema.tsx`, `limpeza-do-sistema.tsx` |

## Limites

| Grupo | Limite (chave) | Padrão | Faixa | Onde vale |
|---|---|---|---|---|
| Pacotes e arquivos | Tamanho máximo do pacote (`package.max_size_mb`) | 200 MB | 1–2048 | Envio de pacote no Catálogo |
| Pacotes e arquivos | Tamanho máximo de cada arquivo (`artifact.max_size_mb`) | 200 MB | 1–2048 | Envio de arquivos (Storage) |
| Execuções | Execuções ao mesmo tempo (`execution.max_concurrent`) | 20 | 1–500 | Entrega da fila: acima disso, os jobs esperam |
| Execuções | Tempo máximo de uma execução (`execution.max_timeout_seconds`) | 4 h | 1 min–7 dias | Teto do tempo limite declarado pela automação |
| Execuções | Repetições automáticas (`execution.max_retries`) | 3 | 0–20 | Teto de novas tentativas declaradas pela automação |
| Agendamentos | Intervalo mínimo entre repetições (`schedule.min_interval_seconds`) | 60 s | 60 s–1 dia | Criar/editar agendamento do tipo intervalo |
| Máquinas | Agents cadastrados (`agent.max_registered`) | 100 | 1–10000 | Registro de um Agent novo (o que já existe sempre se registra de novo) |
| Máquinas | Tamanho máximo de mensagem do Agent (`gateway.max_message_bytes`) | 64 KB | — | Vem do `.env` (`AGENT_GATEWAY_MAX_MESSAGE_BYTES`); muda reiniciando |
| Tempo real | Telas acompanhando ao mesmo tempo (`realtime.max_sse_connections`) | 250 | 10–5000 | Avisos ao vivo (Painel, Fila, Acompanhar). Cheio: 503 e a tela tenta de novo. Contagem por processo |
| Fluxos | Etapas por fluxo (`flow.max_nodes`) | 100 | 1–1000 | Inclusão de nó num fluxo |

Tempo e repetições não mudam a automação: a versão publicada continua igual, e o job é
montado com o menor valor entre o declarado e o teto.

## Limpeza automática do sistema

Roda a cada 30 minutos. Cada regra apaga até 5000 linhas por passada (a próxima continua),
e uma regra com erro não segura as outras. Desligar uma regra ("sem prazo") faz ela não apagar nada.

| Grupo | Regra (chave) | Padrão | Mínimo | O que sai |
|---|---|---|---|---|
| Avisos | Notificações (`notificacoes`) | 7 dias | 2 | Notificações e entregas, lidas ou não. O detector olha 24 h, por isso o mínimo de 2 dias |
| Máquinas | Medições de CPU, memória e disco (`maquinas.recursos`) | 7 dias | 1 | Medições antigas; a última de cada Agent fica |
| Máquinas | Estado da sessão do Windows (`maquinas.sessoes`) | 7 dias | 1 | Idem; o último de cada Agent fica |
| Máquinas | Comandos enviados às máquinas (`maquinas.comandos`) | 30 dias | 7 | Comandos concluídos; pendentes e enviados ficam |
| Máquinas | Diagnósticos das máquinas (`maquinas.diagnosticos`) | 30 dias | 7 | Diagnósticos concluídos |
| Acesso e segurança | Sessões vencidas do modo direto (`acesso.sessoes_diretas`) | 7 dias | 1 | Sessões e desafios vencidos, revogados ou usados |
| Acesso e segurança | Tokens de job vencidos (`acesso.tokens_de_job`) | 7 dias | 1 | Tokens vencidos ou revogados |
| Acesso e segurança | Códigos de cadastro não usados (`acesso.codigos_vencidos`) | 30 dias | 1 | Códigos que venceram sem uso; os usados ficam |
| Comunicação interna | Mensagens internas processadas (`interno.mensagens`) | 30 dias | 7 | Entrada processada e saída publicada; pendentes e com erro ficam |
| Comunicação interna | Proteção contra pedido repetido (`interno.idempotencia`) | 7 dias | 1 | Registros vencidos |
| Execuções | Decisões de despacho (`execucoes.decisoes`) | 90 dias | 30 | Por que cada job foi para tal máquina |
| Execuções | Reconciliações (`execucoes.reconciliacoes`) | 90 dias | 30 | Reconciliações concluídas |
| Execuções | Chamadas de webhook (`execucoes.webhooks`) | 90 dias | 7 | Histórico das chamadas (a proteção contra repetição olha 24 h) |

**Guardado sempre** (aparece na tela só para consulta): auditoria; execuções, etapas e itens;
histórico de tempos (base das estimativas).

**Imagens, logs e arquivos de cada automação** continuam na seção por automação da mesma tela,
**sem prazo padrão** (decisão de 10/11/2026: dados de folha e LGPD; a exclusão não tem volta).

## Como acrescentar uma configuração

1. Acrescente a entrada em `domain/configuracoes.py`, no grupo certo (ou num grupo novo: a
   tela agrupa na ordem do catálogo).
2. **Limite**: chame `ler_limite(db, "<chave>")` no ponto onde ele vale. Sem sessão de banco à
   mão (conexões ao vivo), use `limite_em_cache`.
   **Limpeza**: escreva `(db, corte, lote) -> int` em `<contexto dono da tabela>/infrastructure/limpeza.py`
   (use `apagar_em_lote`) e registre em `LIMPADORES`.
3. Acrescente a linha nas tabelas acima.

O teste `governance/tests/test_configuracoes.py` falha se uma regra editável não tiver quem
apague, se uma chave se repetir ou se um padrão estiver fora da faixa.

## API

| Método | Caminho | Permissão |
|---|---|---|
| GET | `/governance/limites` | `limites.ver` |
| PUT | `/governance/limites/{chave}` `{valor}` | `limites.gerenciar` |
| GET | `/governance/limpeza` | `retencao.ver` |
| PUT | `/governance/limpeza/{chave}` `{dias \| null}` ou `{voltar_ao_padrao: true}` | `retencao.gerenciar` |

As respostas trazem `grupos` (na ordem) e `itens` (catálogo + valor em vigor + última limpeza).
A API antiga `PUT /governance/system-limits/{key}` continua e valida as chaves do catálogo do
mesmo jeito.

## Mudanças de 13/11/2026

- **Corrigido**: cada início do Portal regravava limites e políticas com o padrão, perdendo o
  que alguém tinha mudado. Agora o início só cria o que falta.
- As 10 "políticas por tipo de registro" (`retention_policies`) nunca apagaram nada: saíram da
  tela e do banco (migração `d6e7f8a9b0c2`). A limpeza real é a deste documento.
