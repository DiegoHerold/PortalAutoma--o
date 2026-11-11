# Deployment

O Portal roda nativamente no Windows, sem containers. `scripts/portal.ps1`
concentra instalacao, inicio e parada.

## Requisitos

- Python 3.12: `winget install Python.Python.3.12`.
- Node.js 20 ou superior.
- PostgreSQL 16 ou superior (usado o binario `initdb`/`pg_ctl`).
- Redis como servico do Windows: `winget install Redis.Redis`. O instalador
  escuta em todas as interfaces, sem senha, e cria a regra de firewall `Redis`.
  Depois de instalar, adicione `bind 127.0.0.1` em
  `C:\Program Files\Redis\redis.windows-service.conf`, remova essa regra e
  reinicie o servico.

## Comandos

```powershell
.\scripts\portal.ps1 setup           # virtualenv, backend\.env, banco e build do frontend
.\scripts\portal.ps1 start           # banco, migrations, API, worker, beat e frontend
.\scripts\portal.ps1 status          # 0 quando tudo esta UP, 1 caso contrario
.\scripts\portal.ps1 restart
.\scripts\portal.ps1 stop
.\scripts\portal.ps1 open-firewall   # exige administrador
```

Rode `setup` novamente depois de atualizar o codigo do frontend ou as
dependencias. Ele preserva o `backend\.env` e o banco existentes.

## Componentes

| Componente | Porta | Gerenciado por |
| --- | --- | --- |
| Frontend (Next.js standalone) | 3000 | `portal.ps1` |
| API (uvicorn) | 8000 | `portal.ps1` |
| Worker e beat (Celery) | - | `portal.ps1` |
| PostgreSQL dedicado | 5433, so loopback | `portal.ps1` |
| Redis | 6379, so loopback | Servico do Windows |

O frontend chama a API diretamente na porta 8000, no mesmo host usado para
abrir o site (`frontend/src/lib/constants.ts`).

## Dados

Banco, pacotes, logs e PIDs ficam em `%LOCALAPPDATA%\PortalAutomacoes`.
Defina `PORTAL_DATA_DIR` para usar outra pasta. Inclua essa pasta nos backups.

## Configuracao

- `POSTGRES_SERVER` e `REDIS_URL` usam `127.0.0.1`, nao `localhost`: no Windows
  `localhost` tenta IPv6 primeiro e cada conexao nova perde segundos.
- `BACKEND_PUBLIC_URL` precisa ser acessivel pelas maquinas dos Agents, pois
  compoe as URLs de download de pacotes. O `setup` grava o IP da rede detectado;
  ajuste se o IP da maquina mudar.
- Para usar um PostgreSQL ja existente, crie o banco, ajuste `POSTGRES_*` e
  remova `PORTAL_MANAGED_POSTGRES` do `backend\.env`.
- `STORAGE_BACKEND=local` guarda pacotes em disco. Para um bucket compativel
  com S3, use `STORAGE_BACKEND=s3` e preencha as variaveis `S3_*`.

## Celery no Windows

O worker usa `--pool=threads`, pois o pool `prefork` nao funciona no Windows.

## Rede local

As portas 3000 e 8000 escutam em todas as interfaces. Se outra maquina nao
conseguir acessar, rode `open-firewall`: a regra vale para os perfis Privado e
Dominio, somente na subrede local.

## HTTPS da API

O modo direto do SDK recusa `http://`, e o Agent deve usar `wss://`. Para a API subir
em HTTPS:

1. Peça à CA da empresa um certificado com o nome que as máquinas usam para chegar ao
   Portal (por exemplo `portal.intranet.biason.net`). Guarde a cadeia completa e a chave
   em PEM fora do repositório.
2. No `backend\.env`:

   ```
   PORTAL_TLS_CERT=C:\PortalAutomacoes\tls\portal.pem
   PORTAL_TLS_KEY=C:\PortalAutomacoes\tls\portal-chave.pem
   BACKEND_PUBLIC_URL=https://portal.intranet.biason.net:8000
   ```

3. `.\scripts\portal.ps1 restart`.

Com TLS, o uvicorn aceita só TLS 1.2 e 1.3, com cifras AEAD (`ECDHE+AESGCM` e
`ECDHE+CHACHA20`). O padrão do uvicorn (`TLSv1`) foi trocado porque só oferece cifras
com SHA-1, e um cliente TLS 1.2 moderno não negocia com elas. O health check usa o nome
do certificado, com validação ligada; por isso `BACKEND_PUBLIC_URL` precisa ser `https://`
com esse nome. Sem as duas variáveis, a API continua em HTTP e o `start` mostra um aviso.

As máquinas (Agent e automações diretas) validam o certificado pela CA da empresa,
instalada no repositório do Windows. Não existe opção para desligar a validação.

Limite conhecido: o frontend (Next.js standalone na porta 3000) continua em HTTP. Ver
`docs/fase-1-relatorio.md`.

## Logs

Cada processo grava `<nome>.out.log` e `<nome>.err.log` em
`%LOCALAPPDATA%\PortalAutomacoes\logs`.
