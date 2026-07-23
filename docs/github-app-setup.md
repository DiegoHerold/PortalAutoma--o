# Configurar o GitHub App (integração real, sem mocks)

A importação de automações via GitHub usa um **GitHub App** (não um OAuth App
comum) instalado pela própria Biason na conta/organização que hospeda
`biason-automations`. O Portal nunca guarda um token de usuário — apenas o
`installation_id`, trocando-o por tokens de instalação de curta duração a cada
chamada (`app/integrations/github/client.py`).

Sem este cadastro feito manualmente no GitHub, os endpoints `/integrations/github/*`
respondem 400 com `GithubAppNotConfiguredError` — o código já está pronto e
testado (`tests/domain/test_github_client.py`), falta só o cadastro e as
variáveis de ambiente abaixo.

## 1. Criar o App

1. Acesse `https://github.com/settings/apps/new` (ou, se for para uma
   organização, `https://github.com/organizations/<org>/settings/apps/new`).
2. **GitHub App name**: algo único, ex. `biason-automations-portal`.
3. **Homepage URL**: a URL pública do Portal (frontend).
4. **Callback URL**: não obrigatório para este fluxo (usamos Setup URL).
5. **Setup URL (importante)**: marque "Redirect on update" e defina como
   `https://<backend-publico>/api/v1/integrations/github/callback`.
   É para essa URL que o GitHub redireciona o navegador do usuário depois de
   instalar/atualizar o App — o Portal usa isso para saber que a instalação
   foi concluída e redireciona de volta para `/settings/integrations` no
   frontend (ver `github_integrations.py::callback`).
6. **Webhook**: ativado, apontando para
   `https://<backend-publico>/api/v1/webhooks/github`. Gere um webhook secret
   forte e guarde — vai para `GITHUB_APP_WEBHOOK_SECRET`.
7. **Permissions** (mínimo necessário):
   - Repository → Contents: **Read-only**
   - Repository → Metadata: **Read-only**
   - Repository → Pull requests: não necessário (fora de escopo)
8. **Subscribe to events**: `push`, `installation`, `installation_repositories`.
9. **Where can this GitHub App be installed?**: "Only on this account" a
   menos que outras contas também precisem importar automações.
10. Crie o App.

## 2. Gerar a chave privada

Na página do App recém-criado, em "Private keys", clique **Generate a
private key** — baixa um arquivo `.pem`. Guarde com cuidado: é o segredo mais
sensível dessa integração.

## 3. Instalar o App

Isso normalmente acontece pelo próprio fluxo do Portal (`Conectar GitHub` em
`/settings/integrations`), que redireciona para
`https://github.com/apps/<slug>/installations/new`. Também é possível instalar
manualmente pela mesma URL e selecionar o repositório `biason-automations`
(ou "All repositories", se preferir).

## 4. Preencher o `.env` do backend

```
GITHUB_APP_ID=123456                      # "App ID" na página do App
GITHUB_APP_SLUG=biason-automations-portal # parte final da URL do App
GITHUB_APP_CLIENT_ID=Iv1.xxxxxxxxxxxx     # opcional, não usado no fluxo atual
GITHUB_APP_CLIENT_SECRET=                 # opcional, não usado no fluxo atual
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMII...\n-----END RSA PRIVATE KEY-----\n"
GITHUB_APP_WEBHOOK_SECRET=um-segredo-forte-aqui
```

O conteúdo do `.pem` deve ir em uma única linha com `\n` literais no lugar das
quebras de linha (é assim que `pydantic-settings` lê variáveis multi-linha de
um `.env`). Reinicie o backend depois de preencher.

## 5. Verificar

- `GET /api/v1/integrations/github` deve responder `[]` (sem erro) antes de
  qualquer instalação.
- Clique em "Conectar GitHub" no Portal (`/settings/integrations`) — deve
  abrir a página de instalação real do GitHub.
- Após instalar, o GitHub redireciona de volta e a conta aparece listada,
  com status "Ativa".
- Em "Nova automação → Importar do GitHub", selecione o repositório e a
  branch; o Portal lê `automation-workspace.yaml` na raiz e lista os
  `automation.yaml` encontrados.

## Rotação e revogação

- Para revogar o acesso, desinstale o App pela página de configurações da
  conta/organização no GitHub **ou** use "Desconectar" em
  `/settings/integrations` (isso só remove o registro local; para revogar de
  fato o acesso do App aos repositórios, desinstale também pelo GitHub).
- Para rotacionar a chave privada, gere uma nova em "Private keys" e troque
  `GITHUB_APP_PRIVATE_KEY`; a antiga pode ser revogada em seguida.
