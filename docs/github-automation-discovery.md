# Descoberta de automações no GitHub

Pré-requisito: GitHub App conectado (`docs/github-app-setup.md`).

## `automation-workspace.yaml`

Fica na raiz do repositório e diz onde procurar automações, por exemplo:

```yaml
schema_version: 1
roots:
  - automations/
```

`GithubDiscoveryService.discover()` lê esse arquivo
(`app/domain/automation_manifest.py::parse_workspace_manifest`), pega a árvore
completa do repositório na branch escolhida (`git/trees/{sha}?recursive=1`) e
filtra os `automation.yaml` que estão sob algum dos `roots` configurados
(`discover_manifest_paths`). Repositórios muito grandes (árvore truncada pela
API do GitHub) geram um erro explícito pedindo para reorganizar em menos
arquivos por pasta — a API do GitHub não pagina `git/trees`.

## Por automação encontrada

Para cada `automation.yaml`, o serviço:

1. Lê o conteúdo (`contents/{path}?ref={branch}`, decodificado de base64).
2. Valida o manifesto (mesma validação usada no upload manual).
3. Verifica se aquele `id`+`version` já foi importado antes
   (`already_imported`).
4. Detecta `id` duplicado entre automações do mesmo repositório.

Nada disso baixa ou executa o código de fato — é só leitura de metadados via
API. O download completo da pasta só acontece quando o usuário escolhe
importar (`stage_import`), via `download_directory()` (busca todos os blobs
sob aquele caminho e escreve em um diretório temporário).

## Importação seletiva

`POST /integrations/github/{integration_id}/import` recebe uma lista de
`manifest_paths` e empacota cada automação escolhida individualmente — nunca
o repositório inteiro como uma única automação. Cada uma vira um item de
staging independente, com seu próprio `staging_id`, e precisa ser confirmada
separadamente (mesmo endpoint de confirmação do upload manual).

## Atualizações (webhook `push`)

O webhook `POST /api/v1/webhooks/github` (assinatura HMAC-SHA256 verificada
contra `GITHUB_APP_WEBHOOK_SECRET`) escuta `push` e marca
`AutomationSource.sync_status = "update_available"` quando um commit toca o
caminho de uma automação já importada — sem nunca reimportar sozinho. O botão
"Verificar atualização" na tela da automação (ou `POST
/automations/{id}:sync`) faz a mesma checagem sob demanda, comparando o commit
mais recente do caminho com `last_commit_sha`.

Eventos `installation` (deleted/suspend/unsuspend) atualizam a
`GithubIntegration` local automaticamente.
