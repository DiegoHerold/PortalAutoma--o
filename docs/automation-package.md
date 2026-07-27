# Formato do pacote e do manifesto

Status: vigente com ajuste de capabilities.

Pacotes continuam imutaveis e devem ser baixados pelo Automation Agent por
HTTPS/S3/MinIO. O Agent nunca executa codigo diretamente do GitHub.

## `automation.yaml`

```yaml
schema_version: 1
id: conciliacao-bancaria
name: Conciliacao bancaria
version: 1.2.0
description: Concilia lancamentos do extrato com o razao.
category: financeiro
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
  required:
    - key: browser.playwright
inputs:
  - name: competencia
    type: string
    required: true
```

Capabilities antigas como lista de strings seguem aceitas temporariamente por
compatibilidade, mas novos manifests devem usar objetos tipados conforme
`docs/capabilities.md`.

## Pacote final

```text
package.zip
  automation.yaml
  package-metadata.json
  application/
  resources/
  pyproject.toml
  requirements.txt
```

`build_package` exclui diretorios e arquivos temporarios como `.git/`,
`.venv/`, `__pycache__/`, `tests/`, `.pytest_cache/` e `node_modules/`.

## Dependencias

Se houver `requirements.txt`, o Agent prepara ambiente Python isolado para a
versao da automacao. O cache local pode ser reaproveitado enquanto o hash das
dependencias e do pacote permanecer valido.

## Hash e imutabilidade

- SHA-256 do ZIP final vira `AutomationVersion.artifact_sha256`.
- `(automation_id, version)` deve ser unico.
- O objeto no storage nao e sobrescrito.
- Uma mudanca de codigo exige nova versao.

## Storage

- Local: token temporario de download.
- S3/MinIO: URL pre-assinada.

Arquivos grandes nao passam pelo WebSocket.
