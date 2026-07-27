# Capabilities

Status: vigente.

Capabilities nao devem ser tratadas apenas como strings. O formato oficial e
tipado, versionavel e observado no tempo.

```json
{
  "key": "software.dominio",
  "status": "available",
  "version": "10.5.2",
  "attributes": {
    "installation_path": "C:\\Contabil",
    "interactive_required": true
  },
  "observed_at": "2026-07-27T10:00:00Z"
}
```

Categorias iniciais:

- `os.windows`
- `architecture.x64`
- `desktop.interactive_session`
- `desktop.pywinauto`
- `browser.playwright`
- `browser.chrome`
- `browser.edge`
- `software.dominio`
- `software.excel`
- `runtime.python`
- `runtime.powershell`
- `filesystem.local`
- `network.internet`

## Manifest

```yaml
capabilities:
  required:
    - key: os.windows
      version: ">=10"
    - key: software.dominio
      version: ">=10.4"
    - key: desktop.interactive_session
      attributes:
        unlocked: true
```

O Portal realiza comparacao preliminar. O Agent faz a validacao final local.

## Migracao

Listas antigas como `["playwright", "software.dominio"]` permanecem aceitas
temporariamente por adaptador. Novos manifests devem usar objetos tipados.

