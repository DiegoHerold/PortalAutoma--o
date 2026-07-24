# Formato do pacote e do manifesto

## `automation.yaml`

```yaml
schema_version: 1
id: conciliacao-bancaria          # estável, usado como Automation.key
name: Conciliação bancária
version: 1.2.0                    # semver ou qualquer string única por id
description: Concilia lançamentos do extrato com o razão.
category: financeiro              # opcional; cria a categoria se não existir
runtime:
  id: python
  version: "3.12"
entrypoint:
  type: python-function
  module: app.main
  callable: run
execution:
  interactive_session: false
  timeout_seconds: 900
capabilities:
  required: ["playwright"]
inputs:
  - name: competencia
    type: string
    required: true
```

Validado por `app/domain/automation_manifest.py::parse_automation_manifest`,
que devolve uma lista de erros específicos (campo faltando, tipo errado,
`entrypoint.type` desconhecido) em vez de uma exceção genérica — é isso que
aparece no preview de importação quando o manifesto está inválido.

Só `entrypoint.type: python-function` é suportado por ora — o validador
verifica, via `ast`, que `module` existe entre os arquivos do pacote e que
`callable` é uma função (ou método) declarada nesse módulo, sem importar nada.

## Pacote final (`build_package`)

```
package.zip
├── automation.yaml          # cópia do manifesto original (bytes idênticos)
├── package-metadata.json    # origem (github/manual), quem importou, quando, commit/branch
├── application/             # conteúdo de src/ (ou da raiz, se não houver src/)
├── resources/                # se existir
├── pyproject.toml            # se existir
└── requirements.txt          # se existir (ver "Dependências" abaixo)
```

## Dependências (`requirements.txt`)

Se o pacote tiver um `requirements.txt` na raiz (mesmo nível do
`automation.yaml`), o Automation Agent cria um ambiente virtual Python
isolado só para essa automação (nessa versão específica) e instala essas
dependências nele antes de rodar — em vez de exigir que tudo já esteja
pré-instalado no ambiente compartilhado do Agent. Isso é o que permite usar
Playwright, pandas, pywinauto, openpyxl, ou qualquer outro pacote pip,
inclusive versões diferentes/conflitantes entre automações diferentes.

O ambiente é montado na primeira execução daquela versão e reaproveitado nas
seguintes (só é reconstruído se o conteúdo do `requirements.txt` mudar). Se o
`requirements.txt` listar `playwright`, o Agent roda automaticamente
`playwright install chromium` depois do `pip install`, para baixar o
navegador.

Sem `requirements.txt`, a automação roda direto no interpretador do próprio
Agent (mais rápido para iniciar, mas limitado ao que já está instalado nele —
bom para scripts simples que só usam a biblioteca padrão do Python).

Arquivos deliberadamente excluídos: `.git/`, `.venv/`, `__pycache__/`,
`tests/`, `.pytest_cache/`, `node_modules/` — ver a lista completa em
`build_package`.

`application_type` é `"source"` por padrão (código Python puro, sem build). O
enum já reserva `"wheel"` para quando fizer sentido publicar automações como
wheel pré-compilado — não implementado ainda (fora do escopo desta fase).

## Hash e imutabilidade

- SHA-256 do `.zip` final vira `AutomationVersion.artifact_sha256`.
- `(automation_id, version)` tem `UNIQUE` no banco — tentar confirmar duas
  vezes a mesma versão falha com 409, e reimportar exige subir a versão no
  manifesto.
- O objeto no storage nunca é sobrescrito: o caminho é
  `{automation_key}/{version}/package.zip`.

## Storage

`app/integrations/storage/` — abstração `PackageStorage` com duas
implementações:

- **Local** (`STORAGE_BACKEND=local`): grava em `LOCAL_STORAGE_PATH`; o
  download usa um token JWT de curta duração (`GET
  /automations/artifacts/download?token=...`, 5 min de validade,
  `core/security.py::create_package_download_token`).
- **S3/MinIO** (`STORAGE_BACKEND=s3`, padrão no `docker-compose.yml` local):
  usa `boto3` + URLs pré-assinadas — o Agent baixa direto do MinIO, sem
  passar pelo backend.
