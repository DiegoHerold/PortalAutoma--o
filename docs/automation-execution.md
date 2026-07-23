# Como uma versão importada chega a ser executada

Este catálogo não reimplementa o protocolo do Automation Agent — ele já existe
e funciona (`app/api/v1/endpoints/agents.py` +
`app/services/agent_gateway_service.py`, WebSocket `/agents/ws`,
register/heartbeat/claim-command/finish-command). O que este trabalho
adicionou foi a ponte entre o catálogo novo e esse protocolo já pronto.

## A ponte: `automation_package_resolver.py`

`agent_gateway_service.claim_next_command()` (código pré-existente) monta o
comando que o Agent recebe, incluindo `package_url`/`package_sha256`. Antes,
esses vinham direto dos campos estáticos em `Automation`. Agora:

```python
package_url, package_sha256 = resolve_package_for_dispatch(db, automation)
```

`resolve_package_for_dispatch`:

1. Procura a `AutomationVersion` mais recente com `status="published"` para
   aquela automação.
2. Se encontrar, gera uma URL de download fresca no momento do despacho
   (presigned S3 ou token JWT local) e devolve junto com o hash daquela
   versão.
3. Se não encontrar (automação nunca passou pelo catálogo novo), cai para os
   campos legados `automation.package_url`/`package_sha256` — automações
   cadastradas manualmente antes desta mudança continuam funcionando sem
   qualquer migração de dados.

Isso significa: **importar + confirmar não é suficiente para uma automação
ser despachada** — é preciso publicar a versão (`:activate`) primeiro. Isso é
intencional: dá um ponto de controle explícito antes de qualquer execução em
produção.

## O que o Agent local ainda precisa saber fazer

Fora do escopo desta implementação (por decisão do usuário: só o lado
Portal). Para o Agent funcionar de ponta a ponta com pacotes deste catálogo,
ele precisa, ao receber um comando:

1. Baixar o `.zip` de `package_url` e verificar `package_sha256`.
2. Extrair, localizar `application/` e instalar dependências do
   `pyproject.toml` **em um ambiente isolado por automação** (nunca global —
   requisito de segurança do spec original).
3. Importar `entrypoint.module` e chamar `entrypoint.callable` com o payload
   do job.
4. Reportar eventos de execução de volta pelo protocolo já existente
   (`finish-command`).

Nada disso está implementado neste trabalho — é o próximo passo natural, mas
depende de decisão sobre o executável/instalador do Agent em máquinas
Windows, que ficou deliberadamente fora do escopo desta sessão.
