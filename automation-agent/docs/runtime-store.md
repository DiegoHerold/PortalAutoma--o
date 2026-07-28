# Runtime Store

Armazenamento local imutável de runtimes.

## Estrutura

```
store/
└── runtimes/
    └── python-core/
        └── 3.13/
            └── sha256_abcd1234/
                ├── runtime.json
                ├── content/
                └── verification.json
```

## Fluxo de Importação

```mermaid
graph TD
    CHECK[Consulta local] -->|Presente| USE[Usar runtime existente]
    CHECK -->|Ausente| DL[Download]
    DL --> PARTIAL[downloads/arquivo.partial]
    PARTIAL --> SIZE[Validar tamanho]
    SIZE --> HASH[Validar SHA-256]
    HASH --> SIG[Validar assinatura]
    SIG --> STAGING[Extrair em staging]
    STAGING --> MANIFEST[Validar manifesto]
    MANIFEST --> MOVE[Mover atomicamente para store]
```

## Requisitos

- Download retomável com retry e backoff
- Instalação atômica (staging → store)
- Múltiplas versões coexistentes
- Deduplicação por hash
- Proteção de runtime em uso (não pode ser removido)
- Limpeza de downloads incompletos
- Runtime imutável após validação
