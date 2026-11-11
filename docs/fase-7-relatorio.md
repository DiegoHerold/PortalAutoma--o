# Fase 7: a automação no Catálogo, o botão Executar e campos editáveis

Status: feita e testada, **ainda não aplicada no portal no ar** (precisa reiniciar o portal e
refazer o build da tela). Aguardando sua aprovação.

## Seu pedido (11/11/2026)

> O catálogo deve mostrar ao vivo quando a automação estiver rodando, e o histórico; deve ter
> um botão para acionar a automação, mostrando as empresas e as informações de entrada. Cada
> automação pode ter entradas diferentes: o sistema precisa ser flexível para ver e editar
> esses dados, e o portal deve guardar as informações da automação e editá-las livremente.

Suas decisões:

| Pergunta | Resposta |
|---|---|
| Quem define os campos | **O Portal edita livremente**; o manifesto da automação só sugere os campos iniciais |
| Quem edita campos e valores | **Admin, gestor e quem tem "editar itens"** na automação (concessão por automação) |

## O que mudou

### A página da automação (`/automations/[id]`)

| Aba | O que mostra |
|---|---|
| **Visão geral** | **Agora**: um monitor por execução desta automação, como no Painel (tela ao vivo, etapa, empresa, progresso, falta, término e as últimas linhas do log). **Na fila**: os pedidos desta automação, com quando começam. **Últimas execuções**, com o tempo real ao lado do previsto |
| **Itens** | o cadastro (empresas) com a edição pelas colunas da automação |
| **Campos** | o editor de campos (abaixo) |
| **Histórico** | todas as execuções desta automação, carregando mais conforme pede |
| **Técnico** | o que já existia: versões, gatilhos, agendamentos, preferências e o acesso a telas e logs |

No topo: **Rodando agora** (ou Parada), quantos estão na fila e o botão **Executar**. Na lista
do Catálogo, a automação que está rodando aparece com o selo **Rodando**.

### O botão Executar

1. **Empresas**: busca por código ou nome, "Marcar todos" e "Incluir as filiais de cada matriz
   escolhida". A filial que vai junto com a matriz aparece marcada como "vai com a matriz".
2. **Informações do pedido**: o formulário é gerado pelos campos da automação, com os valores
   padrão já preenchidos.
3. O Portal confere tudo antes de pôr na fila: o campo obrigatório que falta, o tipo errado e o
   campo que não existe aparecem **embaixo do próprio campo**. A competência digitada como
   `102026` vira `10/2026`.

A barra de "Pedir execução" da lista de itens agora abre essa mesma janela, com as empresas
marcadas já escolhidas. Os "parâmetros livres" de nome e valor saíram.

### Campos editáveis

Cada automação tem dois conjuntos de campos, guardados no Portal (`automation_forms`):

- **Informações do pedido**: o que se pede a cada execução (ex.: competência, modo).
- **Colunas de cada item**: o que cada empresa guarda (ex.: pasta de destino, e-mail, separar
  por custo). "Muda o tempo" marca a coluna que entra na estimativa.

Para cada campo dá para editar o nome, o tipo, se é obrigatório, o valor padrão, as opções (se
for uma lista) e o texto de ajuda. Também dá para mudar a ordem e remover. A chave técnica nasce
do nome e não muda depois. Os tipos são:

| Tipo | Aceita |
|---|---|
| Texto, Texto longo, Pasta | até 2.000 caracteres (texto longo: 20.000) |
| Número | `1,5`, `1.234,56`, `2.5` |
| Número inteiro | `42` |
| Sim ou não | sim/não, s/n, 1/0 |
| Data | `31/10/2026` ou `2026-10-31` |
| Mês/ano | `10/2026`, `102026`, `2026-10` (sempre guardado como `MM/AAAA`) |
| Lista de opções | só as opções cadastradas |
| E-mail | um endereço válido |
| Dados avançados (JSON) | qualquer JSON (ex.: rubricas ignoradas) |

Comportamentos:

- Enquanto ninguém edita, valem os campos que o manifesto sugere; ao salvar a primeira vez,
  passam a valer os do Portal.
- Toda mudança vai para a auditoria, com o antes e o depois.
- Se duas pessoas editarem ao mesmo tempo, a segunda é avisada para recarregar em vez de
  sobrescrever.
- **Apagar uma coluna não apaga o dado** já guardado nos itens; ele aparece como "Também guardado".
- Automação que ainda não tem nenhum campo de entrada definido aceita o pedido como antes, sem
  conferir. Assim que ela tem campos, a conferência passa a valer.

**Atenção:** um campo novo criado no Portal chega à automação junto com o pedido, mas só tem
efeito se o código dela ler esse campo. A tela avisa isso.

A Integração Contábil já sugere no manifesto: **Competência** (mês/ano, obrigatória), **O que
fazer** (completo, rubricas ou integração; padrão completo) e **Avisar por e-mail no fim**
(sim). O `dfolha` lê esses três.

## Testes (saída real)

```
backend   (pytest, suíte inteira)                    661 passed in 107.87s
frontend  tsc --noEmit                               sem erros
frontend  npx playwright test                        47 passed (1.6m)
```

No PostgreSQL (`tests/db/test_fase7_campos.py`):

```
campos: manifesto -> portal (v1, auditado); item exige a pasta e guarda o resto;
  pedido sem competência 422, com '102026' -> {'modo': 'completo', 'competencia': '10/2026'}
2 passed
```

Telas (`e2e/fase7.spec.ts`):

```
ok automação: ao vivo, na fila e últimas execuções (claro e escuro)
ok executar: escolher empresas, informações pelos campos, erro ao lado do campo
ok campos: criar, ordenar e salvar; o pedido seguinte usa o campo novo
ok itens: editar usa as colunas da automação e mostra o erro no campo
ok catálogo: a automação que está rodando aparece com o selo
```

### Mutação das regras dos campos (`catalog/domain/formulario.py`)

```
formulario: 345 mutantes · KILLED: 322 · None: 22 · SURVIVED: 1
```

| Sobrevivente | Por que não muda nada |
|---|---|
| `tipo == "texto_longo"` → `tipo >= "texto_longo"` | os únicos tipos que passam por ali são texto, texto_longo e pasta; em ordem alfabética só texto_longo é ≥ "texto_longo" |

Na primeira rodada, 26 mutantes sobreviveram. A maioria era de tipo vindo de fora (de um JSON
ou do banco) comparado com `is`; os testes passaram a usar valores montados em tempo de
execução. Os demais pediam erros que não escondem os seguintes. Reforcei os testes até sobrar
só o equivalente.

### Dois ajustes de testes antigos

- **Fase 5:** o teste de "pedir execução" passou a usar a janela Executar.
- **Fase 6 (notificações):** o teste passava sozinho e falhava na suíte inteira. Outros testes
  ligam o Portal de verdade, e a inicialização dele cria os papéis padrão; o "operador" padrão vê
  as execuções pela permissão antiga por categoria. O Portal estava certo. Agora o teste usa um
  papel sem permissões, e uma conferência mal escrita minha (que contava os e-mails do banco
  inteiro) saiu.

## Telas

| Tela | Arquivo |
|---|---|
| Automação: ao vivo, fila e últimas | [claro](fase-7-telas/automacao-claro.png), [escuro](fase-7-telas/automacao-escuro.png) |
| Executar | [executar.png](fase-7-telas/executar.png) |
| Campos | [campos.png](fase-7-telas/campos.png) |
| Editar item | [editar-item.png](fase-7-telas/editar-item.png) |
| Catálogo com o selo "Rodando" | [catalogo.png](fase-7-telas/catalogo.png) |

## Para aplicar no portal no ar

O portal precisa ser parado e ligado de novo. Isso aplica a migration `c7d8e9f0a1b2`, que é
aditiva (só cria a tabela `automation_forms`). A tela também precisa de um build novo:

```powershell
.\scripts\portal.ps1 stop
cd frontend; $env:NEXT_SEM_CACHE = "1"; npm run build; cd ..
# copiar .next\static e public para .next\standalone (como nas fases anteriores)
.\scripts\portal.ps1 start
```

## O que falta e riscos

- **"Muda o tempo" criado no Portal ainda não entra na estimativa da fila.** A fila lê os
  atributos que mudam o tempo a partir do manifesto. Funciona para as colunas que já vêm do
  manifesto, como `separar_por_custo` na Integração Contábil.
- A edição dos campos não tem histórico de versões para voltar atrás pela tela. Está na
  auditoria (antes e depois).
- Parar uma execução que já está rodando continua sem botão no Portal (ver a Fase 6).
- O portal **não** está pronto para produção.
