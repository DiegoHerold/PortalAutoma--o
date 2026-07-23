# Troubleshooting — catálogo de automações

## "Integração com GitHub não configurada"

`GithubAppNotConfiguredError` — faltam `GITHUB_APP_ID` e/ou
`GITHUB_APP_PRIVATE_KEY` no `.env` do backend. Ver `docs/github-app-setup.md`.

## "GITHUB_APP_SLUG não configurado" ao clicar em Conectar GitHub

O botão precisa montar a URL `https://github.com/apps/<slug>/installations/new`
— preencha `GITHUB_APP_SLUG` com a parte final da URL do App (visível na
página de configurações do App no GitHub).

## Callback do GitHub cai em erro / não conecta

- Confirme que a **Setup URL** cadastrada no App aponta exatamente para
  `https://<backend-publico>/api/v1/integrations/github/callback` (esquema,
  host e porta precisam bater com `BACKEND_PUBLIC_URL`).
- Se o backend estiver atrás de um proxy/túnel, `FRONTEND_URL` precisa
  apontar para uma URL alcançável pelo navegador do usuário (é para lá que o
  callback redireciona no final).

## "A árvore do repositório é grande demais para listar" (truncated=true)

A API do GitHub trunca `git/trees` além de um certo tamanho e não pagina esse
endpoint. Reorganize `automation-workspace.yaml` para apontar para
subpastas menores, ou divida automações grandes por diretório.

## Webhook do GitHub retorna 401

Assinatura inválida — confirme que o **webhook secret** cadastrado no App é
exatamente o mesmo valor de `GITHUB_APP_WEBHOOK_SECRET` no backend.

## Importação trava em "Validando manifesto e empacotando…"

Verifique o tamanho do arquivo contra `MAX_UPLOAD_SIZE_MB` — uploads maiores
que o limite são rejeitados antes mesmo de extrair. Para pacotes GitHub
grandes, o gargalo costuma ser o número de arquivos (cada blob é uma chamada
de API individual) — considere excluir pastas irrelevantes do repositório
(`tests/`, dados de exemplo grandes) da automação antes de importar.

## "Manifesto inválido" mas o YAML parece correto

Rode a mesma validação localmente: os erros vêm de
`app/domain/automation_manifest.py::parse_automation_manifest`, que checa
`schema_version`, `id`, `name`, `version`, `runtime.id`, `entrypoint.type` e
(quando `entrypoint.type == python-function`) `entrypoint.module` +
`entrypoint.callable`. A mensagem de erro já indica qual campo falhou.

## 409 ao confirmar uma importação

Aquela combinação `(automation_id, version)` já existe — versões são
imutáveis por design. Suba o número de versão no `automation.yaml` e
reimporte.

## Versão publicada não aparece no dispatch do Agent

Confira se ela está com `status=published` (não basta `ready` — é preciso
chamar `:activate` explicitamente). O resolver
(`automation_package_resolver.py`) só considera a versão mais recente com
esse status; versões `ready` aguardando publicação são ignoradas de propósito.

## Rodando os testes automatizados

```
cd backend
python3 -m pytest tests/domain -q
```

Cobre manifesto, empacotamento, storage local e autenticação/assinatura do
GitHub App — 39 testes, sem precisar de Postgres/Redis rodando. Testes de
endpoint/serviço que dependem de banco de dados real precisam de
`docker compose up` (ver `docs/deployment.md`); não foram automatizados nesta
sessão por não haver Postgres disponível no ambiente de execução.
