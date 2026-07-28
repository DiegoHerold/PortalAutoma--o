# Manifesto de Automação

Define a estrutura, runtime, entrypoint e recursos de uma automação.

## Formato

```json
{
  "schema_version": 1,
  "id": "portal.processar_documentos",
  "name": "Processar Documentos",
  "version": "1.2.0",
  "runtime": {
    "id": "python-core",
    "version": "3.13"
  },
  "entrypoint": {
    "type": "python_function",
    "module": "automation.main",
    "callable": "run"
  },
  "capabilities": {
    "required": ["windows", "agent.background_execution"]
  },
  "resources": {
    "pool": "background",
    "slots": 1,
    "max_memory_mb": 1024
  },
  "timeout": {
    "execution_seconds": 3600,
    "graceful_shutdown_seconds": 30
  }
}
```

## Tipos de Entrypoint

| Tipo | Descrição | Campos obrigatórios |
|------|-----------|---------------------|
| `python_function` | Função Python | `module`, `callable` |
| `python_module` | Módulo Python (`-m`) | `module` |
| `powershell_script` | Script PowerShell | `script` |
| `executable` | Executável no pacote | `executable_path` |
| `browser_playwright` | Playwright headless | `module`, `callable` |

## Pools

| Pool | Descrição |
|------|-----------|
| `background` | Automações sem interface gráfica |
| `browser` | Automações Playwright headless |
| `interactive` | Reservado para Fase 3 |

## Validação

O validador verifica:

- Presença de `id`, `name`, `version`
- Presença e validade do `runtime`
- Presença e campos do `entrypoint` por tipo
- Modo de execução suportado
- Path traversal em caminhos
- Estrutura do pacote

Erros são retornados de forma estruturada com código, caminho e mensagem.
