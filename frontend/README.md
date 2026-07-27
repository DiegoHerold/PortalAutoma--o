# Frontend

Painel Next.js do Portal de Automacoes. O frontend e interface operacional do
Control Plane e deve falar com o backend por REST e, futuramente, SSE para
atualizacoes em tempo real.

O frontend nao acessa banco diretamente e nao deve decidir estado oficial de
execucoes, Agents ou ofertas.

## Rodando localmente

1. Instale as dependencias com `npm install`.
2. Configure `NEXT_PUBLIC_API_URL`.
3. Rode `npm run dev`.
