"""A linha única do cartão do Painel: cancelando, parando, pausa, espera ou sem sinal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modules.orchestration.application.use_cases.queue import situacao_geral
from modules.telemetry.domain.acompanhamento import EventoDaAutomacao, estado, situacao_do_agora

T0 = datetime(2026, 11, 12, 9, 0, tzinfo=UTC)


def ev(n: int, tipo: str, segundos: float, **payload) -> EventoDaAutomacao:
    return EventoDaAutomacao(f"e{n:03d}", tipo, payload, T0 + timedelta(seconds=segundos), "t1", n)


def _sit(agora_s: float = 60, **kw):
    base = {"job_status": "running", "parada": None, "pausa": None, "espera": None,
            "ultimo_sinal": T0, "desde": T0, "agora": T0 + timedelta(seconds=agora_s)}
    return situacao_do_agora(**{**base, **kw})


def test_rodando_normal_nao_mostra_nada() -> None:
    assert _sit() is None


def test_cancelar_vence_tudo_e_parar_depois_vence_pausa() -> None:
    pausa = {"motivo": "reinicio", "detalhe": "Domínio reiniciada", "desde": T0.isoformat()}
    assert _sit(job_status="cancelling", pausa=pausa)["tipo"] == "cancelando"
    parada = {"tipo": "parar_apos_item", "pedido_em": T0, "recebido_em": None}
    assert _sit(parada=parada, pausa=pausa) == {"tipo": "parando", "desde": T0.isoformat(), "recebido": False}
    assert _sit(parada={**parada, "tipo": "cancelar", "recebido_em": T0})["recebido"] is True
    assert _sit(pausa=pausa)["tipo"] == "pausa"


def test_sem_sinal_so_depois_de_10_minutos() -> None:
    assert _sit(agora_s=599) is None
    assert _sit(agora_s=601) == {"tipo": "sem_sinal", "desde": T0.isoformat()}
    # Sem nenhum evento ainda: conta desde o início da tentativa.
    assert _sit(agora_s=601, ultimo_sinal=None)["tipo"] == "sem_sinal"
    # A espera declarada explica o silêncio: não vira "sem sinal".
    assert _sit(agora_s=3600, espera={"rotulo": "Domínio abrindo", "desde": T0.isoformat()})["tipo"] == "espera"


def test_espera_e_o_ultimo_trecho_so_de_espera() -> None:
    eventos = [
        ev(1, "item.iniciado", 0, item="5066"),
        ev(2, "log", 10, nivel="info", texto="Exportando"),
        ev(3, "log", 20, nivel="info", texto="Ainda esperando a Domínio liberar", espera=True),
        ev(4, "espera.atualizada", 50, desde=(T0 + timedelta(seconds=15)).isoformat(), rotulo="Domínio ocupada"),
    ]
    e = estado(eventos, T0 + timedelta(seconds=60), rodando=True)
    assert e["espera"] == {"rotulo": "Domínio ocupada", "desde": (T0 + timedelta(seconds=15)).isoformat(), "item": None}
    assert e["ultimo_sinal"] == T0 + timedelta(seconds=50)
    # Qualquer outro evento depois encerra a espera.
    depois = estado([*eventos, ev(5, "progresso", 70, atual=3, total=10)], T0 + timedelta(seconds=80), rodando=True)
    assert depois["espera"] is None
    # Log de espera sozinho também conta, com o texto como rótulo.
    so_log = estado(eventos[:3], T0 + timedelta(seconds=30), rodando=True)
    assert so_log["espera"]["rotulo"] == "Ainda esperando a Domínio liberar"
    # Depois do fim não há espera.
    assert estado(eventos, T0 + timedelta(seconds=60), rodando=False)["espera"] is None


def test_pausa_aberta_nao_e_espera() -> None:
    eventos = [ev(1, "pausa.iniciada", 0, motivo="reinicio"), ev(2, "log", 5, nivel="info", texto="Ainda", espera=True)]
    e = estado(eventos, T0 + timedelta(seconds=10), rodando=True)
    assert e["pausa"]["motivo"] == "reinicio" and e["espera"] is None


def test_situacao_geral_da_execucao() -> None:
    assert situacao_geral(["succeeded", "succeeded"]) == "succeeded"
    assert situacao_geral(["succeeded", "cancelled"]) == "partially_succeeded"
    assert situacao_geral(["cancelled", "cancelled"]) == "cancelled"
    assert situacao_geral(["failed", "cancelled"]) == "cancelled"  # uma pessoa parou: não é falha da automação
    assert situacao_geral(["failed", "timed_out"]) == "failed"


def test_cancelamento_sem_resposta_e_sem_comunicacao_vencem_o_resto() -> None:
    prazos = {"aviso_sem_comunicacao": timedelta(seconds=30), "sem_comunicacao": timedelta(minutes=2),
              "prazo_do_cancelamento": timedelta(minutes=2)}
    cancelar = {"tipo": "cancelar", "pedido_em": T0, "recebido_em": None}
    # 1 min depois do pedido: ainda "cancelando".
    assert _sit(agora_s=60, job_status="cancelling", parada=cancelar, **prazos)["tipo"] == "cancelando"
    # 2 min sem resposta: erro, dizendo se a automação chegou a receber.
    assert _sit(agora_s=121, job_status="cancelling", parada=cancelar, **prazos) == {
        "tipo": "cancelamento_sem_resposta", "desde": T0.isoformat(), "recebido": False}
    # Instância calada há 30 s: comunicação não ativa, com a hora em que o Portal cancela.
    calada = _sit(agora_s=45, sinal_da_instancia=T0, **prazos)
    assert calada == {"tipo": "sem_comunicacao", "desde": T0.isoformat(), "cancela_em": (T0 + timedelta(minutes=2)).isoformat()}
    assert _sit(agora_s=20, sinal_da_instancia=T0, **prazos) is None
    # Sem os prazos (modo agente), nada disso aparece.
    assert _sit(agora_s=500, sinal_da_instancia=T0, ultimo_sinal=T0 + timedelta(seconds=499)) is None
