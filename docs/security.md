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

