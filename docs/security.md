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
- O SDK troca o valor por `***` em todo evento antes da fila local; o Portal faz o
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

