# SDK Python do Portal de Automações

Para a automação contar ao Portal o que está fazendo: etapas, itens, progresso, log,
passos com imagem e itens que precisam de uma pessoa. O mesmo código funciona no
**modo agente** (a automação fala só com o Agent local) e no **modo direto** (fala
direto com o Portal por HTTPS). O modo vem da configuração, nunca do código.

Contrato: [`contracts/automation-events/v1`](../../contracts/automation-events/v1/README.md).

## Instalação

```powershell
pip install .\sdk\python            # eventos
pip install .\sdk\python[imagens]   # com imagens dos passos (Pillow)
```

## Uso

```python
from portal_automacoes import Automacao

with Automacao.conectar(versao_automacao="2.3.0") as a:
    with a.etapa("iniciar"):
        a.log("Abrindo a Domínio")
        a.passo("Domínio carregada", tipo="abriu", imagem=print_da_janela())
    for empresa in empresas:
        with a.item(empresa.codigo, rotulo=empresa.nome, grupo=empresa.matriz,
                    configuracao={"separar_por_custo": empresa.separa}):
            with a.etapa("rubricas", tarefas_previstas=len(centros)) as etapa:
                for i, centro in enumerate(centros, 1):
                    a.progresso(i, len(centros), f"centro {centro}")
                    ...
                    etapa.tarefa_concluida()
            if pendentes:
                a.atencao("Rubricas a parametrizar",
                          colunas=[("codigo", "Rubrica"), ("descricao", "Descrição")],
                          linhas=[{"codigo": r.codigo, "descricao": r.descricao} for r in pendentes])
            a.resumo("50 relatórios")
        if a.deve_parar():          # "Parar depois do item atual", pedido no Portal
            break
```

| Método | Evento |
|---|---|
| `with Automacao.conectar()` | `execucao.iniciada` / `execucao.concluida` (`ok`, `erro`, `interrompida`, `atencao`) |
| `with a.etapa(chave, tarefas_previstas=)` | `etapa.iniciada` / `etapa.concluida`; exceção vira `erro`. `tarefas_previstas` é o total da etapa no job; numa retomada, informe o total de novo e chame `tarefa_concluida()` só para o que esta tentativa fizer |
| `with a.item(chave, rotulo=, grupo=, configuracao=)` | `item.iniciado` / `item.concluido` |
| `a.progresso(atual, total, rotulo)` | `progresso` |
| `a.log(texto, nivel="info", espera=False)` | `log` |
| `a.passo(rotulo, tipo="acao", imagem=)` | `passo`; a imagem vai por fora e o evento leva só o id |
| `a.arquivo(caminho, nome=, item=)` | Sem evento: planilha, TXT etc. (até 100 MB) vão para a aba **Arquivos** do Catálogo, ligados à execução e ao item atual |
| `a.espera(rotulo, desde)` | `espera.atualizada` |
| `a.atencao(motivo, colunas, linhas, acoes)` | `atencao` (dentro de um item) |
| `with a.pausa("reinicio", detalhe)` | `pausa.iniciada` / `pausa.concluida`: tempo fora da estimativa |
| `a.deve_parar()`, `a.verificar_parada()`, `a.cancelamento_pedido()` | Consulta os comandos do Portal |
| `a.ao_cancelar(funcao)`, `a.ao_parar(funcao)` | Chamadas na hora em que o pedido chega (0.4.0) |
| `a.email(para, assunto, html=, texto=, cc=, cco=, anexos=, chave=)` | Sem evento: o Portal manda o e-mail (0.5.0) |
| `a.email_enviado_pela_maquina(para, assunto, meio=)` | Sem evento: registra no Portal um e-mail mandado pela máquina |
| `a.segredo(chave, campo=)`, `a.segredos(*chaves)` | Sem evento: acesso (usuário, senha...) ligado à automação no Portal (0.5.0) |

### E-mail pelo Portal (0.5.0)

O padrão é a automação pedir e o Portal mandar (Microsoft Graph, remetente do Portal), com tudo
registrado na tela **E-mails**:

```python
a.email("analista@cliente.com.br", "Folha 10/2026", html="<p>...</p>", cc=["gestor@biason.net"],
        anexos=["resultado.csv"], chave="folha-10-2026")
```

| Situação | O que acontece |
|---|---|
| Aceito | `{"email_id", "situacao": "enviado"}` ou `"na_fila"` (o Graph falhou por um momento; o Portal tenta de novo sozinho) |
| Domínio fora da lista do Portal, anexo proibido (.exe...), dados inválidos | `EmailRecusado` com o motivo (fica registrado no Portal) |
| Anexos acima de 2,5 MB | `EmailRecusado`: entregue com `a.arquivo()` e mande o link |
| Portal fora do ar, execução encerrada, modo agente | `EmailIndisponivel` |
| Modo desligado (desenvolvimento) | Não manda nada; escreve no log local |

Mandou pela máquina (Outlook, SMTP)? Avise: `a.email_enviado_pela_maquina(para, assunto,
meio="outlook", anexos=[...])`. O Portal só registra; se ele não responder, o aviso vai para o log
local e a automação segue. Campos ocultos de segredos viram `***` no assunto e no corpo.

### Segredos (0.5.0)

Senhas e acessos ficam no Portal (Segurança > Segredos), não no `.env` de cada máquina. Um
segredo junta os campos de um acesso (Domínio: usuário, senha e banco):

```python
with Automacao.conectar() as a:
    dominio = a.segredo("dominio")            # Segredo: dominio["usuario"], dominio["senha"], dominio.get("banco")
    senha = a.segredo("dominio", "senha")     # só um campo, em texto
    tudo = a.segredos("dominio", "smtp")      # vários num pedido só
```

1. Cadastre o segredo no Portal com a chave (`dominio`) e os campos. Cada campo é **oculto**
   (senha: nunca aparece no Portal, vira `***` no log) ou **visível** (usuário, banco).
2. Ligue o segredo à automação: aba **Técnico** da automação, bloco **Segredos que usa**.
3. Na execução, `segredo()` pede ao Portal com o token do job. Só sai o que está ligado à
   automação, ativo e dentro da validade, e só enquanto a execução está ativa.

| Situação | O que acontece |
|---|---|
| Liberado | Devolve os campos. Ficam só na memória; o SDK não pede de novo na mesma execução. `repr()` mostra só os nomes |
| Campo que não existe | `KeyError` dizendo quais campos o segredo tem |
| Não ligado, desativado, vencido ou execução encerrada | `SegredoIndisponivel` com a chave e o motivo (nunca o valor) |
| Portal fora do ar | `SegredoIndisponivel` ("Portal indisponível"); a automação decide se espera ou encerra |
| Modo desligado (desenvolvimento) | Lê `PORTAL_SEGREDO_DOMINIO` (JSON com os campos) ou `PORTAL_SEGREDO_DOMINIO__SENHA` (um campo) |
| Modo agente | `SegredoIndisponivel`: o Agent ainda não entrega segredos |

- Os campos ocultos viram `***` em todo evento (log, passo, atenção) antes de ir para a fila
  local, e no log local do SDK. O Portal faz o mesmo ao receber. Valores com menos de 4
  caracteres não são mascarados (apagariam palavras comuns).
- Cada entrega e cada recusa ficam na auditoria do Portal (qual automação, execução e versão).
- Trocar um valor no Portal vale para o próximo pedido; uma execução que já pegou o valor segue
  com ele.

### Parar, cancelar e sem comunicação (0.4.0)

O SDK atende os pedidos do Portal sozinho, em qualquer automação:

| Pedido | O que o SDK faz |
|---|---|
| **Parar depois do item atual** | O próximo `item()`/`iniciar_item()` não começa: levanta `ParadaSolicitada`. Chama `ao_parar` na hora |
| **Cancelar agora** | Chama `ao_cancelar` na hora, e a automação tem 60 s para encerrar sozinha. Sem nada registrado (e sem consultar `deve_parar`), ou passado o prazo, o SDK interrompe a thread principal (`KeyboardInterrupt`, como um Ctrl+C) e registra a execução como interrompida |
| **2 min sem falar com o Portal** | Avisa no log local na primeira falha ("tentando por até 120 s") e, sem retorno, cancela do mesmo jeito: a automação não segue às cegas |
| **O Portal encerrou o job** (401/409) | Cancela do mesmo jeito |

- Quando a automação roda num processo só dela (`portal-automacoes trabalhar -- comando`), o SDK
  encerra o processo 15 s depois da interrupção, se ela continuar presa (código de saída 130).
- Rodando dentro do `trabalhar(instancia, executar)`, a interrupção do SDK não derruba o
  `trabalhar`: ele avisa e espera o próximo job. Erro inesperado da automação também não o
  derruba. O Ctrl+C de uma pessoa continua saindo.
- Prazos: `PORTAL_PRAZO_CANCELAR_S` (60) e `PORTAL_LIMITE_SEM_PORTAL_S` (120).

```python
with Automacao.conectar(segundo_plano=True) as a:
    a.ao_cancelar(lambda: lote.cancelar(a.motivo_da_parada))   # fecha o programa na hora
    a.ao_parar(lambda: setattr(lote, "parar", True))           # termina o item e para
    ...
```

Garantias:

- Falha do Agent ou do Portal **nunca derruba a automação**: o evento fica numa fila em
  disco e é reenviado na ordem, sem duplicar.
- Evento fora do contrato é erro de programação e levanta `EventoInvalido` na hora.
- Imagem vazia, de uma cor só ou corrompida nunca sai da máquina.
- Arquivo entregue com o Portal fora do ar fica pendente e é tentado de novo até `fechar()`;
  o que não sair até lá é avisado no log local (o arquivo continua no disco). No modo agente,
  o arquivo é copiado para a pasta de artefatos da tentativa e o Agent o envia.

## Configuração

| Variável | Modo | Uso |
|---|---|---|
| `PORTAL_MODO` | todos | `agente`, `direto` ou `desligado`. Sem ela: agente se houver pipe, direto se houver `PORTAL_URL`, senão desligado |
| `AUTOMATION_EVENTS_PIPE`, `AUTOMATION_EVENTS_TOKEN` | agente | Entregues pelo ExecutionHost |
| `PORTAL_URL` | direto | `https://...` (http é recusado) |
| `PORTAL_JOB_ID`, `PORTAL_JOB_TOKEN` | direto | Job e token do job; `Instancia.ambiente_do_job` os monta a partir do job recebido |
| `PORTAL_CA_ARQUIVO` | direto | CA da empresa em PEM, se ela não estiver no repositório do Windows |
| `PORTAL_FILA_DIR` | todos | Pasta da fila local |
| `PORTAL_PRAZO_CANCELAR_S` | todos | Prazo para a automação parar sozinha depois de "cancelar" (60) |
| `PORTAL_LIMITE_SEM_PORTAL_S` | agente, direto | Tempo sem comunicação até cancelar a execução (120) |

Não existe opção para desligar a validação do certificado.

## Máquina sem Agent: a instância pede os próprios jobs

Precisa do extra `direto` (`pip install portal-automacoes-sdk[direto]`).

```python
from portal_automacoes import Automacao
from portal_automacoes.instancia import Instancia, trabalhar

# Uma vez por máquina, com o código que o administrador gerou na automação (vale 30 min):
Instancia.inscrever("https://MAQ65.intranet.biason.net:8000", codigo="ABCD-EFGH-JKLM-NPQR",
                    nome="integracao-contabil", arquivo_ca=r"C:\caminho\Biason-Intranet-Root-CA.crt")

# Depois, sempre: espera jobs e roda um por vez.
def executar(job, ambiente):
    with Automacao.conectar(versao_automacao="2.0.0", ambiente=ambiente) as a:
        for item in job.itens:
            with a.item(item["chave"], rotulo=item.get("rotulo")):
                ...

trabalhar(Instancia.carregar("integracao-contabil"), executar, declaracao=montar_declaracao)
```

`declaracao` (um dicionário ou uma função que o monta) é enviada assim que a instância pode
receber jobs. Com ela, o Portal fica sabendo, sem cadastro manual:

```python
{
  "versao": "2.0.0",
  "parametros": [{"chave": "competencia", "rotulo": "Competência", "tipo": "mes_ano", "obrigatorio": True}],
  "itens": {"nome": "Empresa", "chave": "codigo", "grupo": "matriz_codigo",
            "colunas": [{"chave": "caminho_saida", "rotulo": "Pasta de destino", "tipo": "pasta"}]},
  "tabela": [{"chave": "5081", "rotulo": "Matriz", "atributos": {"caminho_saida": r"F:\Folha\5081"}}]
}
```

- `parametros`: o que o Portal pede ao executar. O Portal **só acrescenta**: campo novo entra,
  o que foi editado lá continua como está, e o que a automação deixou de mandar fica
  "fora de uso" (não some).
- `tabela`: vira uma **prévia** na aba Itens; alguém com "editar itens" aprova ou descarta.
- Pela linha de comando: `portal-automacoes trabalhar --nome folha --declaracao declaracao.json -- ...`

- A chave privada é gerada na máquina e fica cifrada pelo DPAPI, no escopo do usuário que
  inscreveu: outro usuário ou outra máquina não a usa. O arquivo fica em
  `%LOCALAPPDATA%\PortalAutomacoes\instancias\`.
- Até o administrador aprovar a instância e escolher a máquina, `trabalhar` só espera.
- Para automações que já existem, em que item e etapa começam e terminam em pontos
  diferentes do código: `iniciar_item`, `concluir_item`, `iniciar_etapa`,
  `concluir_etapa`. A emissão pode vir de mais de uma thread.

## Simuladores e testes

`simuladores/` tem o Agent Service simulado (que roda o **ExecutionHost.exe real**), o
Portal simulado do modo direto (HTTPS com CA própria) e uma automação de exemplo que roda
igual nos dois modos.

```powershell
..\..\backend\.venv\Scripts\python.exe -m pytest -q tests
cd ..\..\backend; .venv\Scripts\python.exe -m pytest -q tests\integration\test_automacao_dois_modos.py
```
