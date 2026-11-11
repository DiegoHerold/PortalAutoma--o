# Fase 8: a automação se declara ao conectar, e os arquivos que ela entrega

Status: pronta para a sua aprovação. **Não está no ar**: precisa do deploy abaixo.

## Seu pedido (11/11/2026)

> "precisa que no catálogo de automações tenha as configurações das entradas. e preciso que isso
> seja dinâmico, toda vez que eu conectar a automação no portal já deve trazer todas essas
> informações de variáveis de entrada para executar, a tabela de dados se possuir, e se vai
> entregar alguma coisa como uma planilha ou um arquivo deve ter um espaço uma aba também dentro
> do catálogo de automações que vai ficar salvo, que nada mais que são os artefatos que ficaram
> no armazenamento"

Suas decisões:

| Pergunta | Decisão |
|---|---|
| Quando a automação manda os campos e o Portal já tem os dele | **Junta, só acrescenta.** Campo novo entra; o que foi editado no Portal fica; o que a automação deixou de mandar fica "fora de uso" (não some) |
| A tabela de dados que a automação manda | **Prévia para alguém aprovar** na aba Itens |
| Quem vê e baixa os arquivos | **Quem pode ver telas e logs** da automação; todo download na auditoria |

## O que mudou

### Ao conectar, a automação se declara

Assim que a instância está aprovada e pode receber jobs, o SDK manda ao Portal
(`POST /api/v1/direto/declaracao`):

- **`parametros`**: o que o Portal pede ao executar (ex.: competência, modo, aviso por e-mail);
- **`itens`**: o que é um item (nome, chave, grupo) e as colunas dele;
- **`tabela`**: o cadastro de itens da automação (na Integração Contábil, o `empresas.db` com as
  rubricas ignoradas).

O Portal junta os campos com o que já tem, sempre pelas regras acima, e audita cada mudança
(`automacao.declarada`, com a instância como autor). Declaração inválida volta 422 com o motivo
de cada campo, e a automação continua pegando jobs com o que o Portal já tinha.

Ajuste encontrado pelos testes: quando alguém salvava as Entradas no Portal, o navegador
mandava os campos sem a marca de origem, e o Portal passava a tratá-los como "criados no Portal".
Aí a automação não conseguia mais marcar um campo dela como fora de uso. Agora o Portal guarda
a origem e o "fora de uso" que já tinha e não aceita essas duas marcas do navegador.

### Catálogo: abas Entradas, Itens e Arquivos

| Aba | O que tem |
|---|---|
| **Visão geral** | Novo bloco "Para executar": o que a automação pede (obrigatórios com *), sem os campos fora de uso |
| **Entradas** (antes "Campos") | Cada campo mostra "da automação" e, se for o caso, "fora de uso". Editar continua livre |
| **Itens** | Aviso "A automação mandou o cadastro de empresas dela": **Ver e aprovar** (tudo ou só algumas linhas; o que tem erro não entra) ou **Descartar**. A prévia é recalculada contra o cadastro atual, e uma tabela igual à do cadastro não deixa nada pendente |
| **Arquivos** (nova) | Planilhas, TXT e o `resultado.csv` de cada lote, com o item, a hora e o tamanho. Busca por nome ou código. **Baixar** leva o token no cabeçalho (nunca na URL) e cada download vai para a auditoria (`automacao.arquivo.baixado`) |

O **Executar** não pede mais os campos fora de uso.

### Arquivos entregues

- O SDK ganhou `a.arquivo(caminho, nome=, item=)`. O arquivo vai por fora dos eventos
  (`PUT /direto/jobs/{job}/arquivos`, até 100 MB, token do job no cabeçalho) e vira artefato da
  execução no armazenamento (bucket `arquivos-entregues`).
- Com o Portal fora do ar, o arquivo espera e é tentado de novo até o fim da execução. O que não
  sair até lá é avisado no log local, e o arquivo continua no disco. No modo agente, o SDK copia
  o arquivo para a pasta de artefatos e o Agent envia.
- As imagens dos passos continuam fora desta aba: elas seguem o prazo de imagens.

### Retenção

Em Governança > Retenção entrou o prazo **"Arquivos entregues"** por automação. Sem prazo, nada
sai. Com prazo, a limpeza de hora em hora apaga os bytes pelo Storage, marca o arquivo como
apagado (o download responde 410) e registra na auditoria.

### SDK 0.3.0

- `Instancia.declarar(dict)`.
- `trabalhar(..., declaracao=dict ou função)`: declara de novo se a instância voltar a ser aprovada.
- `Automacao.arquivo(...)`.
- Na linha de comando: `portal-automacoes trabalhar --declaracao arquivo.json -- ...`.

### Integração Contábil (dfolha)

- `dfolha central trabalhar` declara as entradas de `portal/automacao.json`, as colunas do item e
  o cadastro local (`dados/empresas.db`, com as rubricas ignoradas). A declaração é montada a cada
  conexão.
- A dfolha entrega, por empresa, o resumo de rubricas, as rubricas pendentes e os TXT, com o
  código da empresa na frente do nome; no fim, o `resultado.csv` do lote.
- **Com SDK antigo (0.2.0)**, a dfolha avisa "atualize o SDK" e continua funcionando como hoje,
  sem declarar e sem entregar arquivos. Assim, a ordem em que você atualiza a .194 não quebra nada.
- Guia atualizado: `Integração contabil/docs/ligar-ao-portal.md`, partes 5 e 6.

## Testes (saída real)

| Suíte | Resultado |
|---|---|
| Backend completo (PostgreSQL de teste, migrations do zero) | **723 passed** (antes da fase: 665) |
| Ponta a ponta: Portal real (uvicorn, HTTP interno) + SDK real | passou: declara ao conectar → competência nas Entradas, tabela em prévia → arquivo entregue, listado e baixado |
| Declaração e arquivos no banco (`test_fase8_declaracao_arquivos.py`) | 2 passed: pendente 403; edição do Portal vale; "modo" fora de uso não é exigido; prévia aprovada/descartada; download só com "ver telas e logs", auditado; retenção de 30 dias apaga o TXT velho (410) e mantém o resto |
| SDK | **71 passed** (13 novos: arquivo no modo direto e agente, Portal fora do ar, declaração no `trabalhar`) |
| Integração Contábil (dfolha) | **493 passed**, inclusive a declaração conferida pelo **validador real do Portal** e os arquivos por empresa no job simulado |
| Telas (Playwright) | **57 passed**, todas as fases |

Mutação das regras novas (`tools/mutacao/rodar.py`):

| Módulo | Mortos | Vivos | Os vivos |
|---|---|---|---|
| `catalog/domain/declaracao.py` | 54 | 1 | `nome and chave` → `or`: equivalente (sem um dos dois a declaração já é recusada) |
| `catalog/domain/formulario.py` | 354 | 2 | `origem <= "automacao"` (só existem "automacao" e "portal") e `tipo >= "texto_longo"` (nenhum tipo é maior): equivalentes |

A mutação achou um defeito real: chave e grupo do item maiores que 60 caracteres eram
**cortados sem aviso** (o corte trocaria a chave por outra). Agora são recusados com o motivo.
Os testes também acharam a perda da marca "da automação" ao salvar as Entradas no Portal
(corrigido, ver acima).

## Também nesta entrega: máquinas e times (pedido de 11/11/2026)

**Apagar máquina** (Máquinas > Gerenciar > Máquinas cadastradas > Apagar), admin ou gestor:

- antes de apagar, a tela mostra o que depende da máquina: automações diretas, Agents e
  pedidos da fila marcados para rodar só nela;
- com vínculo, só apaga com **"Apagar mesmo assim"**. As automações ficam **sem máquina** (a
  instância volta a esperar aprovação, onde se escolhe outra), o Agent fica sem máquina e os
  pedidos da fila podem ir para qualquer máquina que sirva;
- com execução rodando nela, não apaga (nem confirmando);
- a máquina sai do cadastro, das telas e da fila. O histórico das execuções que rodaram nela
  continua com o nome, e o nome fica livre para uma máquina nova. Auditado (`maquina.removida`);
- a **Local Simulated Worker** do portal no ar não tem nada ligado a ela: apaga direto.

**Times** (Pessoas e acesso > Times > Membros e permissões). Sua escolha: as duas formas.

- **Membros**: adicionar e tirar pessoas;
- **Por categoria**: ver e executar todas as automações da categoria;
- **Por automação**: as mesmas ações de "Acesso a telas e logs" (ver execuções, ver telas e
  logs, editar itens, executar, controlar);
- no **cadastro do usuário** (criar ou editar), escolher os times da pessoa;
- quem entra no time ganha as permissões dele, somadas às suas; quem sai perde; time
  desabilitado não dá nada;
- conferido com login de verdade (token) no banco de teste;
- toda mudança vai para a auditoria.

Testes desta parte: 18 unitários (regras do time e de apagar máquina) e 2 no banco, já dentro
das 723 do backend; e 3 de tela, já dentro das 57.

Migration `e9f0a1b2c3d4` (aditiva):
- tabela `access_team_category_permissions`;
- coluna `machines.removida_em`;
- o nome da máquina passa a ser único só entre as não apagadas.

Telas: [apagar com vínculos](times-e-maquinas-telas/apagar-maquina-com-vinculos.png),
[máquinas depois](times-e-maquinas-telas/maquinas-depois.png),
[time](times-e-maquinas-telas/time-membros-e-permissoes.png),
[times no usuário](times-e-maquinas-telas/usuario-times.png).

## Telas

| Tela | Arquivo |
|---|---|
| Entradas com origem e "fora de uso" | [entradas.png](fase-8-telas/entradas.png) |
| Itens: aviso da tabela da automação | [itens-previa.png](fase-8-telas/itens-previa.png) |
| Itens: aprovar só o escolhido | [itens-aprovar.png](fase-8-telas/itens-aprovar.png) |
| Arquivos | [claro](fase-8-telas/arquivos-claro.png), [escuro](fase-8-telas/arquivos-escuro.png) |
| Retenção com o prazo de arquivos | [retencao-arquivos.png](fase-8-telas/retencao-arquivos.png) |

## Para aplicar

**1. Portal (MAQ65).** Parar e ligar de novo aplica as migrations `d8e9f0a1b2c3` (Fase 8) e
`e9f0a1b2c3d4` (times e máquinas). As duas são aditivas.

```powershell
.\scripts\portal.ps1 stop
cd frontend; $env:NEXT_SEM_CACHE = "1"; npm run build; cd ..
# copiar .next\static e public para .next\standalone (como nas fases anteriores)
.\scripts\portal.ps1 start
```

**2. SDK na .194.** A branch `sdk-python` no GitHub ainda está na 0.2.0. Preciso da sua
autorização para publicar a 0.3.0 nela. Depois, na .194, rode o mesmo comando de instalação da
parte 3.1 do guia, com `--upgrade`.

**3. dfolha na .194.** Leve o código novo da Integração Contábil como nas vezes anteriores e rode
de novo `dfolha central trabalhar`. Na primeira conexão:

- a aba Itens mostra o cadastro para você aprovar;
- as Entradas ficam marcadas "da automação".

## O que falta e riscos

- **A tabela da automação manda e-mails e pastas dos clientes ao Portal.** É o mesmo conteúdo que a
  importação do `empresas.db` já leva. Só quem edita itens vê a prévia, e nada entra no cadastro
  sem aprovação.
- **Os arquivos têm valores da folha.** Ficam protegidos por "ver telas e logs", com download
  auditado e prazo opcional. Sem prazo definido, ficam para sempre: o prazo padrão continua
  "sem padrão", como você decidiu na Fase 6.
- **O arquivo que não sai até o fim da execução não é reenviado depois.** O SDK guarda na fila
  local só os eventos, não os arquivos. Fica o aviso no log local, e o arquivo continua na pasta
  da empresa.
- **O modo agente ainda não foi testado com o Agent real**: o SDK copia o arquivo para a pasta de
  artefatos, e o envio é do Agent. A Integração Contábil usa o modo direto, que está testado de
  ponta a ponta.
- **Quem baixa um arquivo precisa da concessão "ver telas e logs" na automação.** Só o
  administrador passa direto. O gestor e as demais pessoas precisam da concessão em Técnico >
  Acesso a telas e logs, a mesma regra das telas da Fase 4.
- O portal **não** está pronto para produção.
