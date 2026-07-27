# ADR-016 - Reestruturacao incremental do backend

## Contexto

O backend atual contem codigo util, mas mistura nomes legados, infraestrutura,
contratos de API e regras de dominio em varios pontos. A solicitacao vigente e
reorganizar profundamente a arquitetura sem recriar o projeto do zero e sem
apagar codigo funcional que ainda pode ser migrado.

## Decisao

Adotaremos uma reestruturacao incremental para um monolito modular. O codigo
existente sera classificado como KEEP, MOVE, REFACTOR, REPLACE ou DELETE antes
de qualquer remocao definitiva. O novo codigo oficial ficara em
`backend/modules`, com contextos de dominio claros e camadas
`domain/application/infrastructure/api/tests` quando aplicaveis. O pacote
`backend/app` pode continuar existindo como adaptador temporario ate que os
casos de uso sejam movidos.

## Alternativas consideradas

- Recriar o backend do zero: rejeitado por perder comportamento validado,
  migrations e integracoes existentes.
- Manter a arquitetura atual e apenas renomear classes: rejeitado por nao criar
  fronteiras de propriedade nem contratos de longo prazo.
- Dividir em microsservicos agora: rejeitado por aumentar custo operacional
  antes de estabilizar o dominio.

## Consequencias

As mudancas passam a ocorrer em etapas rastreaveis. Cada modulo deve declarar
propriedade de entidades, portas de aplicacao e contratos. Endpoints antigos
podem sobreviver como camada de compatibilidade, desde que deleguem para os
novos casos de uso e nao dupliquem regra de negocio.

## Riscos

Durante a transicao, nomes legados como Job e Worker ainda podem aparecer nas
APIs e no frontend. Tambem ha risco de duplicacao se adaptadores antigos forem
mantidos sem data de retirada.

## Impacto de migracao

A migracao exige mover services e modelos de forma gradual, mantendo testes de
arquitetura para impedir que dominio novo dependa de FastAPI, SQLAlchemy ou
protocolos de transporte. A remocao de codigo legado so deve ocorrer depois de
substituicao funcional e validacao.
