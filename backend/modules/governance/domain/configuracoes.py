"""Catálogo das configurações do sistema: limites e limpeza automática.

É o único lugar que lista o que o Portal configura. Cada entrada diz o nome, para que
serve, o valor padrão, a faixa aceita e onde ela vale. Para criar uma configuração nova:

1. acrescente a entrada aqui (no grupo certo);
2. ligue o consumidor: limite -> ``ler_limite(db, CHAVE)`` no ponto onde ele vale;
   limpeza -> uma função no contexto dono da tabela, registrada em
   ``modules/governance/infrastructure/adapters/limpeza.py``;
3. descreva em ``docs/configuracoes.md``.

Sem linha gravada no banco, vale o padrão daqui: a configuração já funciona na instalação
e uma mudança no padrão chega a quem nunca a alterou.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


class ConfiguracaoInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Limite:
    chave: str
    grupo: str
    nome: str
    descricao: str
    unidade: str          # mb | segundos | quantidade | bytes
    padrao: int
    minimo: int
    maximo: int
    onde_vale: str
    # "portal": muda na tela e vale na hora. "arquivo": vem do .env e só muda reiniciando.
    origem: str = "portal"
    variavel_de_ambiente: str | None = None


@dataclass(frozen=True)
class Limpeza:
    chave: str
    grupo: str
    nome: str
    descricao: str
    o_que_sai: str
    padrao_dias: int | None
    minimo_dias: int
    maximo_dias: int = 3650
    # Regras fixas aparecem na tela só para consulta: o Portal nunca apaga esses dados sozinho.
    editavel: bool = True


# --------------------------------------------------------------------------- limites

LIMITES: tuple[Limite, ...] = (
    # Pacotes e arquivos
    Limite("package.max_size_mb", "Pacotes e arquivos", "Tamanho máximo do pacote",
           "Maior pacote de automação aceito no envio.", "mb", 200, 1, 2048,
           "Envio de pacote no Catálogo."),
    Limite("artifact.max_size_mb", "Pacotes e arquivos", "Tamanho máximo de cada arquivo",
           "Maior arquivo que uma execução pode entregar (planilha, TXT, imagem).", "mb", 200, 1, 2048,
           "Envio de arquivos pelas execuções e pelo Storage."),
    # Execuções
    Limite("execution.max_concurrent", "Execuções", "Execuções ao mesmo tempo",
           "Quantos jobs podem rodar juntos em todas as máquinas. Acima disso, os jobs esperam na fila.",
           "quantidade", 20, 1, 500, "Entrega da fila às máquinas."),
    Limite("execution.max_timeout_seconds", "Execuções", "Tempo máximo de uma execução",
           "Teto para o tempo limite declarado pela automação. Uma automação que pede mais recebe este valor.",
           "segundos", 14400, 60, 604800, "Montagem do job a partir da versão publicada."),
    Limite("execution.max_retries", "Execuções", "Repetições automáticas",
           "Teto de novas tentativas quando uma execução falha. Uma automação que pede mais recebe este valor.",
           "quantidade", 3, 0, 20, "Montagem do job a partir da versão publicada."),
    # Agendamentos
    Limite("schedule.min_interval_seconds", "Agendamentos", "Intervalo mínimo entre repetições",
           "Menor intervalo aceito num agendamento do tipo intervalo.", "segundos", 60, 60, 86400,
           "Criação e edição de agendamentos."),
    # Máquinas
    Limite("agent.max_registered", "Máquinas", "Agents cadastrados",
           "Quantos Agents podem ser cadastrados. Um Agent que já existe sempre pode se registrar de novo.",
           "quantidade", 100, 1, 10000, "Registro de um Agent novo."),
    Limite("gateway.max_message_bytes", "Máquinas", "Tamanho máximo de mensagem do Agent",
           "Maior mensagem que um Agent pode mandar pelo canal de comunicação.", "bytes", 65536, 1024, 10485760,
           "Canal de comunicação com os Agents.", origem="arquivo",
           variavel_de_ambiente="AGENT_GATEWAY_MAX_MESSAGE_BYTES"),
    # Tempo real
    Limite("realtime.max_sse_connections", "Tempo real", "Telas acompanhando ao mesmo tempo",
           "Quantas conexões de atualização ao vivo (painel, fila, execução) o Portal mantém abertas juntas. "
           "Acima disso, a tela tenta de novo em alguns segundos.", "quantidade", 250, 10, 5000,
           "Avisos ao vivo do Painel, da Fila e do Acompanhar."),
    # Fluxos
    Limite("flow.max_nodes", "Fluxos", "Etapas por fluxo",
           "Quantos nós uma versão de fluxo pode ter.", "quantidade", 100, 1, 1000,
           "Inclusão de nó num fluxo."),
)


# --------------------------------------------------------------------------- limpeza

LIMPEZAS: tuple[Limpeza, ...] = (
    # Avisos
    Limpeza("notificacoes", "Avisos", "Notificações",
            "Avisos do sino (erro, atenção, término, máquina offline, fila parada).",
            "Notificações e as entregas delas, lidas ou não, mais antigas que o prazo.",
            7, 2, 365),
    # Máquinas
    Limpeza("maquinas.recursos", "Máquinas", "Medições de CPU, memória e disco",
            "Medições que os Agents mandam a cada sinal de vida.",
            "Medições mais antigas que o prazo. A última de cada Agent sempre fica.",
            7, 1, 365),
    Limpeza("maquinas.sessoes", "Máquinas", "Estado da sessão do Windows",
            "Se a sessão estava livre ou bloqueada em cada sinal de vida.",
            "Registros mais antigos que o prazo. O último de cada Agent sempre fica.",
            7, 1, 365),
    Limpeza("maquinas.comandos", "Máquinas", "Comandos enviados às máquinas",
            "Comandos do Portal para os Agents e para as automações em modo direto.",
            "Comandos já concluídos (confirmados, falhos ou entregues) mais antigos que o prazo. Pendentes ficam.",
            30, 7, 3650),
    Limpeza("maquinas.diagnosticos", "Máquinas", "Diagnósticos das máquinas",
            "Diagnósticos pedidos pelo Portal aos Agents.",
            "Diagnósticos concluídos mais antigos que o prazo.",
            30, 7, 3650),
    # Acesso e segurança
    Limpeza("acesso.sessoes_diretas", "Acesso e segurança", "Sessões vencidas do modo direto",
            "Sessões e desafios de login das automações em modo direto.",
            "Sessões e desafios vencidos ou revogados há mais tempo que o prazo.",
            7, 1, 365),
    Limpeza("acesso.tokens_de_job", "Acesso e segurança", "Tokens de job vencidos",
            "Credencial temporária que cada job usa para falar com o Portal.",
            "Tokens vencidos ou revogados há mais tempo que o prazo.",
            7, 1, 365),
    Limpeza("acesso.codigos_vencidos", "Acesso e segurança", "Códigos de cadastro não usados",
            "Códigos para cadastrar Agents e automações em modo direto.",
            "Códigos que venceram sem uso há mais tempo que o prazo. Os usados ficam.",
            30, 1, 3650),
    # Comunicação interna
    Limpeza("interno.mensagens", "Comunicação interna", "Mensagens internas processadas",
            "Fila de mensagens entre as partes do Portal (entrada e saída).",
            "Mensagens já processadas ou publicadas mais antigas que o prazo. Pendentes e com erro ficam.",
            30, 7, 3650),
    Limpeza("interno.idempotencia", "Comunicação interna", "Proteção contra pedido repetido",
            "Registro que impede o mesmo pedido de ser feito duas vezes.",
            "Registros vencidos há mais tempo que o prazo.",
            7, 1, 365),
    # Execuções
    Limpeza("execucoes.decisoes", "Execuções", "Decisões de despacho",
            "Por que cada job foi para uma máquina e não para outra.",
            "Decisões mais antigas que o prazo.",
            90, 30, 3650),
    Limpeza("execucoes.reconciliacoes", "Execuções", "Reconciliações",
            "Correções feitas quando Portal e máquina discordam do estado de um job.",
            "Reconciliações concluídas mais antigas que o prazo.",
            90, 30, 3650),
    Limpeza("execucoes.webhooks", "Execuções", "Chamadas de webhook",
            "Histórico de cada chamada recebida pelos webhooks.",
            "Chamadas mais antigas que o prazo.",
            90, 7, 3650),
    # Guardado sempre (consulta)
    Limpeza("sempre.auditoria", "Guardado sempre", "Auditoria",
            "Quem fez o quê e quando. Prova de cada mudança.",
            "Nada. A auditoria não é apagada pelo Portal.", None, 0, editavel=False),
    Limpeza("sempre.execucoes", "Guardado sempre", "Execuções, etapas e itens",
            "O histórico de cada execução e do andamento dela.",
            "Nada. Imagens, logs e arquivos de cada automação têm prazo próprio, na seção por automação.",
            None, 0, editavel=False),
    Limpeza("sempre.tempos", "Guardado sempre", "Histórico de tempos",
            "Base das estimativas de duração.",
            "Nada. Apagar mudaria as estimativas.", None, 0, editavel=False),
)

LIMITES_POR_CHAVE = {item.chave: item for item in LIMITES}
LIMPEZAS_POR_CHAVE = {item.chave: item for item in LIMPEZAS}


def limite(chave: str) -> Limite:
    try:
        return LIMITES_POR_CHAVE[chave]
    except KeyError as exc:
        raise ConfiguracaoInvalida(f"Limite desconhecido: {chave}.") from exc


def limpeza(chave: str) -> Limpeza:
    try:
        return LIMPEZAS_POR_CHAVE[chave]
    except KeyError as exc:
        raise ConfiguracaoInvalida(f"Regra de limpeza desconhecida: {chave}.") from exc


def validar_limite(chave: str, valor: int) -> int:
    item = limite(chave)
    if item.origem != "portal":
        raise ConfiguracaoInvalida(f"{item.nome} vem do arquivo .env ({item.variavel_de_ambiente}) e muda reiniciando o Portal.")
    if not isinstance(valor, int) or not item.minimo <= valor <= item.maximo:
        raise ConfiguracaoInvalida(f"{item.nome}: use um número inteiro de {item.minimo} a {item.maximo}.")
    return valor


def validar_prazo(chave: str, dias: int | None) -> int | None:
    """``None`` desliga a regra (nada sai)."""
    item = limpeza(chave)
    if not item.editavel:
        raise ConfiguracaoInvalida(f"{item.nome} é guardado sempre e não tem prazo.")
    if dias is not None and (not isinstance(dias, int) or not item.minimo_dias <= dias <= item.maximo_dias):
        raise ConfiguracaoInvalida(f"{item.nome}: use de {item.minimo_dias} a {item.maximo_dias} dias, ou deixe sem prazo.")
    return dias


def corte(agora: datetime, dias: int | None) -> datetime | None:
    return None if dias is None else agora - timedelta(days=dias)
