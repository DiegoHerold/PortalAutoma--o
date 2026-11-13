# Webhooks

Status: vigente (13/11/2026). Substitui o webhook antigo (`/webhooks/trigger/...`,
`/triggers/...`), que responde 410.

Um webhook é uma URL para um sistema de fora (ERP, Power Automate, script) **acionar uma
automação**. Só isso: não lê nada do Portal, não muda cadastro, não vê execuções. Para um sistema
que precisa usar a API do Portal (ler o Histórico, acompanhar uma execução), use uma
**conta de serviço**.

## Chamar

```http
POST /api/v1/webhooks/{id}
Authorization: Bearer wht_...
Content-Type: application/json
Idempotency-Key: pedido-123            (opcional)

{"parametros": {"competencia": "10/2026"}, "itens": ["101", "102"], "com_filiais": true}
```

- `parametros`: os campos de entrada da automação (aba Entradas). Conferidos como no botão
  Executar: obrigatório, tipo, padrão; campo desconhecido é recusado.
- `itens`: as chaves dos itens (ex.: códigos das empresas), se a automação trabalha com itens.
  `com_filiais` (padrão `true`) inclui as filiais de cada matriz.
- Corpo vazio vale para automação sem campos obrigatórios e sem itens.
- O pedido entra na **Fila**, com a versão publicada mais recente, como o Executar. A execução
  aparece no Histórico com origem `webhook` e pedido por `webhook:{id}`.

| Resposta | Quando |
|---|---|
| `202 {"execucao_id", "itens", "situacao": "na_fila"}` | Aceita |
| `200 {"execucao_id", "situacao": "repetida"}` | `Idempotency-Key` já aceita nas últimas 24 h: nada novo foi criado |
| `400` | Token na URL ou no corpo; JSON inválido |
| `401` | Sem token, token errado ou webhook inexistente (a mesma resposta) |
| `403` | Webhook desligado; IP fora da lista |
| `413` / `415` | Corpo acima de 64 KB; não é JSON |
| `422` | Campos ou itens inválidos (`detalhe` com o motivo de cada campo); chave desconhecida no corpo |
| `429` | Acima do limite de chamadas por minuto do webhook |

## Segurança

- **Token** `wht_...` só no cabeçalho `Authorization: Bearer`. Na URL (`?token=`, `?secret=`...)
  ou no corpo é recusado. Aparece uma única vez; o Portal guarda o SHA-256 e os 4 últimos
  caracteres. "Novo token" corta o anterior na hora.
- **IPs permitidos** (opcional): IPs ou redes (`10.0.8.15`, `10.0.9.0/24`). O IP é o da conexão;
  o Portal não confia em `X-Forwarded-For`.
- **Limite por minuto** (padrão 30, até 600), contado no banco (vale com mais de um processo).
- **Desligar** pausa sem perder o cadastro.
- **Histórico**: toda chamada a um webhook existente (aceita, repetida ou recusada, com motivo,
  IP e execução) fica em `webhook_chamadas` e aparece no detalhe do webhook. Criar, mudar, gerar
  token e apagar vão para a auditoria (`webhook.*`). O token nunca é gravado.

## Gestão (API com login)

| Rota | Permissão |
|---|---|
| `GET /webhooks?automacao=` | `webhooks.ver` ou `automacoes.ver`; só das automações que a pessoa vê |
| `POST /webhooks` (`automation_id`, `nome`, `descricao`, `ips_permitidos`, `limite_por_minuto`) → `{webhook, token}` | `webhooks.gerenciar` e poder **executar** a automação |
| `PUT /webhooks/{id}` (os mesmos campos e `ativo`) | idem |
| `POST /webhooks/{id}/token` → `{webhook, token}` | idem |
| `DELETE /webhooks/{id}` | idem |
| `GET /webhooks/{id}/chamadas?limite=` | `webhooks.ver` |

## Migração

Os webhooks de antes viraram webhooks novos **desligados e sem token** (migration
`c5d6e7f8a9b1`): o endereço e o token mudaram. Para cada um: gere o token, ligue e atualize o
sistema que chama. O mapeamento de campos do webhook antigo não existe mais: o corpo segue o
formato acima. Os gatilhos "em cadeia" não fazem parte dos webhooks e saíram (nunca tiveram quem
os disparasse); condições entre automações ficam para os fluxos.

Código: `backend/modules/orchestration/webhooks/` (regras em `aplicacao.py`).
