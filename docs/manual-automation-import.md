# Importação manual por ZIP

Alternativa ao GitHub, com o mesmo resultado interno — útil quando a
automação não vive em `biason-automations` ou o GitHub App ainda não está
configurado.

## Formato esperado do ZIP

```
minha-automacao.zip
├── automation.yaml        # obrigatório, na raiz do zip OU dentro de uma única pasta
├── src/                    # vira "application/" dentro do pacote final
├── resources/              # opcional
├── pyproject.toml          # opcional
└── tests/                  # ignorado ao empacotar
```

Se o `.zip` contém uma única pasta na raiz (padrão comum de export do
GitHub, `repo-branch/...`), `find_single_root_dir` "desce" um nível
automaticamente antes de procurar o manifesto.

## Passo a passo (`ManualUploadService.import_from_zip`)

1. Upload é gravado em arquivo temporário com limite de tamanho
   (`MAX_UPLOAD_SIZE_MB`), calculando SHA-256 do zip original.
2. Extração protegida contra zip-slip (`safe_extract_zip` — cada entrada é
   resolvida e checada contra o diretório destino antes de gravar; testado
   com um payload malicioso `../../etc/passwd`).
3. Localiza o único `automation.yaml` (`locate_single_manifest` — erro claro
   se houver zero ou mais de um).
4. Valida o manifesto e o entrypoint **sem importar o código** — o
   entrypoint `python-function` é checado com o módulo `ast` (parse estático,
   confirma que a função existe no módulo declarado sem executar nada; ver
   `validate_entrypoint_on_disk`).
5. Empacota (`build_package`) e envia ao storage configurado.
6. Se válido e ainda não importado, cria uma entrada de staging (mesma trilha
   que o GitHub usa) e devolve um preview para o usuário revisar.

## Confirmar ou descartar

- `POST /automations/import/{staging_id}/confirm` — persiste
  `AutomationSource(type=manual_upload)` + `AutomationVersion(status=ready)`.
  Aceita `category_id` opcional (senão usa a categoria sugerida pelo
  manifesto, criando-a se ainda não existir).
- `DELETE /automations/import/{staging_id}` — descarta o staging sem tocar o
  banco (o objeto já gravado no storage fica órfão; aceitável para o MVP,
  pode ganhar um job de limpeza depois).

## Limites e validações

- Tamanho máximo: `MAX_UPLOAD_SIZE_MB` (env), padrão 200 MB.
- TTL do staging: `IMPORT_STAGING_TTL_SECONDS` (env), padrão 30 min — depois
  disso o `staging_id` expira e a confirmação retorna 410.
- Reimportar a mesma `(automation_id, version)` é bloqueado com 409 —
  versões são imutáveis; suba um número de versão novo no manifesto.
