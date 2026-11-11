# Ligar uma automação ao Portal (automação externa, modo direto)

Status: vigente desde 11/11/2026. Complementa o ADR-018 (modos de conexão).

Uma **automação externa** já está instalada na máquina dela (o código, o Python, a planilha,
o ERP). O Portal não leva pacote nem runtime: ele decide **o que** roda e **onde**, e a
automação pede o trabalho ao Portal e conta o que está fazendo. A máquina só faz conexão de
saída; nenhuma porta é aberta nela. Serve para qualquer automação nova.

## O que o Portal sabe dela: o manifesto

Um arquivo JSON (ou YAML) com:

| Campo | Para quê |
|---|---|
| `automation.id`, `name`, `version` | identidade; `id` é a chave da automação no Portal |
| `entrypoint.type: "externa"` | publica **sem pacote nem runtime**; o job vai sempre para a instância direta, nunca para um Agent |
| `execution.mode` | `tela` (ocupa a máquina sozinha), `segundo_plano` ou `navegador` |
| `itens` | o que é um item (empresa, CNPJ, cliente...): chave, grupo, atributos (JSON Schema) e quais atributos mudam o tempo do trabalho |
| `etapas` | as etapas com `por_item` e `por_tarefa`: é o que dá as estimativas |

Exemplo real: `Integração contabil/portal/automacao.json`.

## Passo a passo

1. **Cadastro** (uma vez, com um administrador): `POST /automations`, `POST /automations/{id}/versions`
   com o manifesto e `POST /automation-versions/{id}/publish`. Os itens entram pela tela de Itens
   ou pela importação. A Integração Contábil tem um script que faz tudo:
   `scripts/registrar_no_portal.py`.
2. **Inscrição da máquina**: o Portal gera um código de uso único (Máquinas > Gerenciar, ou
   `POST /automations/{id}/instancias-diretas/codigos`). Na máquina:
   `portal-automacoes inscrever --portal <url> --codigo <código> --nome <nome>`.
   A chave privada fica no DPAPI do Windows (só aquele usuário, naquela máquina).
3. **Aprovação**: no Portal, escolhendo a máquina.
4. **Trabalho**: `portal-automacoes trabalhar --nome <nome> -- <comando da automação>` (qualquer
   linguagem) ou, em Python, `trabalhar(instancia, executar)`.

## O que a automação faz

```python
from portal_automacoes import Automacao, job_atual

job = job_atual()                     # parametros e itens do pedido
with Automacao.conectar(segundo_plano=True) as a:
    for item in job["itens"]:
        with a.item(item["chave"], rotulo=item["rotulo"]):
            with a.etapa("conferir") as etapa:
                ...
                etapa.tarefa_concluida()
                a.passo("Abriu: Relatório", imagem=print_da_tela)
            if a.deve_parar():        # o Portal pediu para parar
                break
```

Automações que já existem (como o `dfolha`) usam a forma sem bloco: `iniciar_item`/`concluir_item`,
`iniciar_etapa`/`concluir_etapa`, `iniciar_pausa`/`concluir_pausa`, `log`, `progresso`, `atencao`.

- **`segundo_plano=True`** (recomendado em RPA): quem emite nunca espera a rede. Com o Portal
  fora do ar, os eventos ficam numa fila local em disco e saem quando ele volta; as imagens são
  puladas (o passo entra só com o texto).
- Evento fora do contrato é recusado na hora (`EventoInvalido`): o contrato está em
  `contracts/automation-events/v1`.
- Credencial nunca vai na URL nem na linha de comando: o token do job vai por variável de ambiente
  do processo e no cabeçalho.

## HTTP provisório

Decisão de 11/11/2026: "não precisa usar https vindo da automação por enquanto". O SDK aceita
`http://` **só** com `--permitir-http` (ou `permitir_http=True`) e **só** para endereço da rede
interna (IP privado, nome de máquina, `.local`, `.intranet.biason.net`). Endereço público em HTTP é
sempre recusado. Sem TLS, as telas e o log trafegam sem criptografia na rede interna: quando o
certificado do Portal estiver instalado, inscreva de novo com `https://` e sem a opção.
