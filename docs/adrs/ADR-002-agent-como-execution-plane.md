# ADR-002 - Agent como Execution Plane

Status: aceito.

## Contexto

Execucoes dependem de recursos locais, sessoes interativas, softwares e
isolamento que so existem na maquina de execucao.

## Decisao

O Automation Agent e o execution plane. Ele observa a maquina, valida ofertas,
prepara pacotes/runtimes, executa, monitora, envia eventos e faz upload de
artefatos.

## Alternativas consideradas

- Portal acessar diretamente o desktop remoto.
- Portal instalar runtimes diretamente na maquina.

## Consequencias

O Agent pode rejeitar ofertas mesmo selecionado pelo Portal. O Portal precisa
reconciliar observacoes locais sem confiar cegamente nelas.

## Riscos

Agents desatualizados podem falar protocolo legado e exigir adaptadores por um
periodo de transicao.

## Impacto de migracao

`Worker` sera decomposto em `Agent`, `AgentInstance`, capabilities, snapshots e
politicas administrativas.
