# ADR-020 - Redesenho do frontend com a identidade Biason

Status: aceito em 09/11/2026. Substitui o ADR-017.

## Contexto

O ADR-017 preservou o frontend durante a reestruturação do backend. O Portal passa a
acompanhar várias automações em várias máquinas, e a referência de experiência é o
portal local da Integração Contábil: imagens ao vivo, logs e estimativas sempre visíveis.
A identidade atual (grafite e marigold) não é a da Biason.

## Decisao

Refazer a camada visual inteira, em todas as telas, com a identidade Biason:

- Referência de experiência: portal da Integração Contábil.
- Referência de identidade: Biason Comunica (navy, névoa, areia, Barlow, eyebrow com
  tracinho) e as regras de marca (`#142845` como âncora).
- Tema claro e escuro, ambos por tokens.
- Imagens ao vivo, logs e estimativas presentes em toda lista de execução, máquina e
  automação; Central de telas para administradores.

Continua valendo do ADR-017: nada de mock permanente; sem dado, estado vazio real.
Componentes e chamadas de API são reaproveitados onde fizer sentido.

## Alternativas consideradas

- Manter o design atual e só acrescentar telas: mistura duas identidades.
- Biblioteca de UI externa: a camada própria de componentes já existe e atende.

## Consequencias

`docs/design-system.md` será reescrito na Fase 3. O `AGENTS.md` deixa de proibir o
redesenho.

## Riscos

Regressão visual em telas administrativas pouco usadas. Mitigação: verificação com
Playwright em desktop e celular, tema claro e escuro, sem erro no console.

## Impacto de migracao

As telas migram por fase: design system e Fila na Fase 3, execução na Fase 4, Painel e
Máquinas na Fase 5, telas administrativas na Fase 6.
