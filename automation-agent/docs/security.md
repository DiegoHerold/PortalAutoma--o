# Segurança — Fase 2

## Validações Implementadas

### Integridade de Artefatos
- SHA-256 obrigatório para runtimes e pacotes
- Assinatura digital preparada (DevelopmentSignatureVerifier em dev)
- Em produção: pacotes sem assinatura são rejeitados

### Proteção de Arquivos
- Path traversal bloqueado em extração de ZIPs
- ZIP bomb detectado via ratio de compressão (limite: 100x)
- Limite de tamanho descompactado (padrão: 2048 MB)
- Validação de extensão de executáveis (.py, .ps1, .exe)

### Isolamento de Processos
- Cada automação em processo separado (ExecutionHost.exe)
- Job Object para isolar árvore de processos
- Workspace exclusivo por tentativa
- Browser com profile isolado

### Segredos
- **Nunca em linha de comando** (aparecem na lista de processos)
- Configuração via arquivo temporário protegido (deletado após leitura)
- Variáveis de ambiente do processo (não globais)
- Redação de valores sensíveis em logs
- Nenhuma credencial em texto puro no SQLite

### Auditoria
- Todos os downloads registrados
- Todas as execuções persistidas
- Decisões do Admission Controller persistidas
- Eventos de execução com sequência monotônica

## Configuração

```json
{
  "Security": {
    "RequireHashVerification": true,
    "RequirePackageSignature": false,
    "BlockPathTraversal": true,
    "AllowedExecutableExtensions": [".py", ".ps1", ".exe"]
  }
}
```

## Restrições

- Nenhum pacote não validado pode ser executado
- A automação nunca escreve no Package Store
- Não execute diretamente conteúdo de Git
- Não execute do diretório de download
- Runtime e pacote imutáveis após validação
