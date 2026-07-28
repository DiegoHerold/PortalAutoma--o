# Cache e Limpeza

## Cache Manager

Gerencia o ciclo de vida de runtimes, pacotes e workspaces armazenados localmente.

### Status do Cache

```powershell
AgentService.exe cache status
```

Retorna:
```json
{
  "runtime_store_size_mb": 450,
  "runtime_count": 2,
  "package_store_size_mb": 120,
  "package_count": 5,
  "downloads_size_mb": 0,
  "total_size_mb": 570
}
```

### Limpeza

```powershell
AgentService.exe cache cleanup
```

## Políticas de Limpeza

1. **Downloads parciais** — Removidos após 24h
2. **Diretórios de staging** — Removidos após 6h
3. **Pacotes LRU** — Evicção por Last Recently Used quando excede limite
4. **Workspaces stale** — Removidos após 24h

## Proteções

Nunca são removidos:
- Runtime em uso por execução ativa
- Pacote em uso por execução ativa
- Workspace de execução em andamento
- Download em progresso
- Artefato referenciado por execução pendente

## Configuração

```json
{
  "Storage": {
    "MinimumFreeDiskMb": 2048
  }
}
```
