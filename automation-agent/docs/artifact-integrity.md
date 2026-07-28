# Verificação de Integridade

## SHA-256

Obrigatório para todos os runtimes e pacotes. Calculado via `SHA256.HashDataAsync` em streaming.

## Assinatura Digital

Preparada com interface `ISignatureVerifier`. Em desenvolvimento, usa `DevelopmentSignatureVerifier` (requer `Environment=Development` + `AllowUnsignedArtifacts=true`). Em produção, pacotes sem assinatura são rejeitados.

## Proteções

| Verificação | Descrição |
|-------------|-----------|
| `HASH_MISMATCH` | SHA-256 não confere |
| `PATH_TRAVERSAL_DETECTED` | Arquivo tenta escapar do diretório |
| `ARCHIVE_BOMB_DETECTED` | Ratio de compressão excede limite (100x) |
| `PACKAGE_TOO_LARGE` | Tamanho descompactado excede 2048 MB |
| `MANIFEST_INVALID` | Manifesto malformado ou incompleto |
| `SIGNATURE_REQUIRED` | Assinatura obrigatória em produção |

## Extração Segura

1. Extrair em diretório de staging
2. Verificar cada entrada do ZIP contra path traversal
3. Calcular ratio de compressão
4. Verificar tamanho total descompactado
5. Mover atomicamente para o store somente após todas as validações
