# ADR-017 - Preservacao do frontend e do design

Status: substituido pelo ADR-020 em 09/11/2026.

## Contexto

O foco desta etapa e a arquitetura do backend. O frontend atual possui layout,
componentes, navegacao, tokens visuais e fluxos que devem ser preservados para
evitar regressao visual e retrabalho fora do escopo.

## Decisao

O frontend nao sera apagado, recriado ou redesenhado nesta reestruturacao. A
reconexao com o backend novo sera feita por adaptadores e atualizacoes de tipos,
preservando telas, componentes e design existentes. Quando um dado ainda nao
estiver disponivel no novo backend, a tela pode usar estados vazios reais, mas
nao mocks permanentes.

## Alternativas consideradas

- Reconstruir frontend junto com backend: rejeitado por misturar escopo visual
  com refatoracao de dominio.
- Congelar frontend sem documentar contratos: rejeitado por dificultar a
  reconexao posterior.
- Manter mocks para simular o backend novo: rejeitado porque mascara lacunas de
  integracao.

## Consequencias

O documento `docs/frontend-integration.md` passa a ser o mapa oficial de
compatibilidade entre telas existentes, endpoints atuais e modulos novos. O
backend deve fornecer contratos consistentes antes de alterar tipos TypeScript.

## Riscos

Algumas telas ainda usam termos legados como Jobs e Workers. A convivencia
temporaria pode confundir ownership se os adaptadores nao forem bem isolados.

## Impacto de migracao

A migracao frontend ocorrera depois da estabilizacao dos modulos Catalog, Fleet,
Orchestration, Dispatch e Telemetry. As alteracoes devem trocar contratos e
tipos sem redesenhar a experiencia visual.
