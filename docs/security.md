# Seguranca

Status: vigente.

## Portal

O Portal e responsavel por:

- Autenticacao e autorizacao.
- Auditoria.
- Segredos e politicas.
- Controle de publicacao de pacotes.
- Hash, assinatura e compatibilidade.
- URLs temporarias para downloads/uploads.
- Estado oficial de execucoes, ofertas, eventos e artefatos.

O Portal nao executa automacoes localmente como regra principal, nao acessa o
desktop do Agent, nao instala runtimes em maquinas remotas e nao executa codigo
diretamente do GitHub.

## Segredos (13/11/2026)

- Guardados cifrados (Governance, `LocalFernetSecretCipher`); o valor nunca volta por
  rota de gestao, nem para quem os gerencia.
- Cada segredo e ligado as automacoes que o usam. A automacao pede pelo SDK
  (`a.segredo("chave")`) com o token do job: so sai durante a execucao, se o segredo
  esta ativo, ligado aquela automacao e dentro da validade. Resposta sem cache.
- Cada entrega e cada recusa ficam na auditoria (`segredo.entregue`, `segredo.negado`),
  com automacao, execucao e versao, sem o valor.
- Um segredo tem campos (usuario, senha, banco...), cifrados juntos numa versao. Campo
  oculto nunca volta por rota de gestao; campo visivel aparece no Portal.
- O SDK troca os campos ocultos por `***` em todo evento antes da fila local; o Portal faz o
  mesmo ao receber. Valores com menos de 4 caracteres nao sao mascarados.
- Modo agente: ainda nao entrega segredos (ver `known-gaps.md`).

## Contas de servico (13/11/2026)

- Para sistemas que chamam a API. Cada conta tem um usuario tecnico com um papel e
  times, como uma pessoa; nunca o papel Administrador.
- Credencial `psa_...` mostrada uma unica vez; o Portal guarda o SHA-256 e os 4
  ultimos caracteres. So no cabecalho `Authorization: Bearer`, nunca na URL.
- Recusa (desativada, vencida, credencial trocada, usuario tecnico inativo) responde
  401 e vai para a auditoria (`conta_de_servico.recusada`), sem a credencial.
- O usuario tecnico nao entra pela tela de login, nao aparece em Usuarios e nao e
  alterado por la. As requisicoes de alteracao ficam na auditoria no nome dele, com o
  id da conta.

## E-mail centralizado (13/11/2026)

- Todo e-mail sai pelo Portal (Microsoft Graph, credencial de aplicativo do `.env`; aceita os
  nomes `ENTRA_*` do Biason Comunica). Liga sozinho com os quatro dados; `NOTIFICACOES_EMAIL_LIGADO`
  força. Os testes forçam desligado (`backend/conftest.py`).
- A automação pede com o token do job e só para domínios permitidos (o do remetente sempre);
  fora disso o pedido é recusado e registrado. Sem executáveis, até 2,5 MB de anexos.
- Conteúdo dos anexos apagado depois do envio (ficam nome e tamanho). O HTML guardado aparece na
  tela num iframe isolado (sem scripts, sem acesso ao Portal).

## Webhooks (13/11/2026)

- So acionam uma automacao (pedido pela Fila, campos e itens conferidos pelo formulario).
- Token `wht_...` so no cabecalho `Authorization: Bearer`; na URL ou no corpo e recusado.
  O Portal guarda o SHA-256; o token aparece uma vez.
- Webhook inexistente e token errado dao a mesma resposta (401).
- IPs/redes permitidos opcionais (IP da conexao; `X-Forwarded-For` ignorado), limite por
  minuto contado no banco, `Idempotency-Key` de 24 h, corpo JSON ate 64 KB.
- Toda chamada fica em `webhook_chamadas`, sem o token. Detalhes em `webhooks.md`.

## Agent

O Agent e responsavel por:

- Identidade local segura.
- Validacao final da oferta.
- Preparacao local isolada.
- Execucao e encerramento de processos.
- Spool offline.
- Upload de artefatos por canal apropriado.

O Agent nao decide versoes oficiais, nao publica pacotes, nao cria execucoes
oficiais e nao contem credenciais do GitHub do Portal.

## Pacotes e runtimes

Fluxo oficial:

```text
GitHub/Upload -> Pipeline/validacao -> Pacote imutavel -> Storage -> Agent
```

Pacotes e runtimes sao imutaveis. O Agent baixa, verifica hash/assinatura,
prepara cache local isolado e executa somente apos commit do Portal.

