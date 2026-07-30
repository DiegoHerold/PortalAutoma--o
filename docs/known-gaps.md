# Gaps conhecidos

Status: vigente.

## Upload resumable de pacotes de automacao

Pacotes grandes sao enviados atualmente em um unico PUT, seja para uma URL
pre-assinada real quando o storage oferecer isso, seja para a API do Portal
quando `upload_url` vier nulo. O frontend apresenta progresso de upload, mas
nao oferece retomada apos interrupcao.

Para suportar redes instaveis e arquivos muito grandes, o backend devera
futuramente implementar upload multipart/resumable com criacao das partes,
envio individual, retomada e finalizacao transacional.

## Metadados de secret e auditoria estruturada

O Catalogo de Secrets nao possui endpoint para consultar o historico de
`SecretVersion`. A criacao e a rotacao retornam metadados da versao criada,
mas a listagem de secrets nao inclui a expiracao da versao atual. Por isso, a
interface nao infere expiracao, nao inventa historico e nunca oferece consulta
do valor protegido.

`GET /governance/audit-events` aceita busca geral, tipo de ator, recurso,
acao, intervalo de datas, limite e deslocamento, mas nao retorna um total nem
aceita filtro por `correlation_id`. A interface mostra eventos da mesma
correlacao apenas dentro da pagina carregada. O backend precisara expor filtro
por correlacao e uma contagem total para permitir uma sequencia completa.

## Access multi-organizacao

Organizacoes, times e contas de servico podem ser atualizados ou removidos. A
remocao de organizacoes e bloqueada enquanto houver usuarios, times, contas de
servico ou configuracoes de governanca vinculadas. O backend ainda nao expoe
contratos de membership para listar, adicionar ou remover usuarios de um time.

Contas de servico nao possuem filtro `organization_id` no endpoint de listagem,
nem rotacao de credencial ou reativacao. O recorte por organizacao nessa tela e
aplicado somente sobre a listagem autorizada retornada pela API, e a interface
deixa a limitacao clara.
