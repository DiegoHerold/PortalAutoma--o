# Execution Workspace

Cada tentativa de execução recebe um diretório exclusivo.

## Estrutura

```
executions/
└── exec_456/
    └── att_001/
        ├── input/           ← Dados de entrada (input.json)
        ├── workspace/       ← Diretório de trabalho da automação
        ├── output/          ← Resultado (output.json, metrics.json)
        ├── artifacts/       ← Artefatos gerados pela automação
        ├── logs/            ← stdout.log, stderr.log, execution-host.log
        ├── temp/            ← Arquivos temporários, config, browser data
        └── execution.json   ← Metadados da execução
```

## Regras

- Runtime e pacote são referenciados (não copiados) a partir do Store
- A automação nunca escreve no Package Store
- Workspace é limpo após 24h (configurável)
- Cada tentativa tem diretório próprio
- Sem compartilhamento de workspace entre execuções
