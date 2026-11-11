"""Detectar ocorrências: o que entra, fila parada por tempo escolhido e nada repetido."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from modules.telemetry.application.use_cases.notificacoes import DetectarOcorrencias
from modules.telemetry.domain.notificacoes import Pessoa

AGORA = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


class Leitor:
    def __init__(self, terminadas=(), atencoes=(), sinais=None, ultimo_inicio=None) -> None:
        self._t, self._a, self._s, self._u = list(terminadas), list(atencoes), sinais or {}, ultimo_inicio
        self.desde: list[datetime] = []
        self.sinais_lidos = 0

    def terminadas(self, desde):
        self.desde.append(desde)
        return self._t

    def atencoes(self, desde):
        self.desde.append(desde)
        return self._a

    def ultimos_sinais(self):
        self.sinais_lidos += 1
        return self._s

    def ultimo_inicio(self):
        return self._u


class Avisos:
    def __init__(self, pessoas, ja=()) -> None:
        self._p = pessoas
        self.ja = set(ja)
        self.gravadas: list[tuple[str, list]] = []

    def pessoas(self):
        return [(p, f"usuario-{p.user_id}") for p in self._p]

    def registradas(self, chaves):
        return {c for c in chaves if c in self.ja}

    def registrar(self, o, para):
        if o.chave in self.ja:
            return False
        self.ja.add(o.chave)
        self.gravadas.append((o.chave, para))
        return True


class Tx:
    vezes = 0

    def commit(self):
        self.vezes += 1


def _fila(maquinas=(), jobs=()):
    chamadas: list[datetime] = []

    def ver(agora):
        chamadas.append(agora)
        return {"maquinas": list(maquinas), "jobs": list(jobs)}

    return ver, chamadas


def _detectar(leitor, avisos, ver_fila, pode=lambda u, a: True):
    return DetectarOcorrencias(leitor, avisos, ver_fila, pode, Tx(), agora=lambda: AGORA)


def test_fim_e_atencao_entram_e_a_janela_e_de_24_horas() -> None:
    leitor = Leitor(terminadas=[{"execution_id": "e1", "situacao": "failed", "automation_id": 7, "automacao": "Folha",
                                 "quando": AGORA, "falha": None}],
                    atencoes=[{"execution_id": "e2", "item": "5081", "motivo": "x", "automation_id": 7, "automacao": "Folha",
                               "quando": AGORA},
                              {"execution_id": "e2", "item": "5081", "motivo": "repetida", "automation_id": 7,
                               "automacao": "Folha", "quando": AGORA}])
    avisos = Avisos([Pessoa(1, "a@x.com", False, frozenset({"erro", "atencao"}))])
    ver, chamadas = _fila()
    r = _detectar(leitor, avisos, ver).execute()
    assert r == {"ocorrencias": 2, "avisos": 2}
    assert avisos.gravadas == [("fim:e1", [(1, "a@x.com")]), ("atencao:e2:5081", [(1, "a@x.com")])]
    assert leitor.desde == [AGORA - timedelta(hours=24)] * 2
    assert chamadas == [] and leitor.sinais_lidos == 0  # ninguém quer máquina nem fila: não lê


def test_ja_registrada_nao_volta() -> None:
    leitor = Leitor(terminadas=[{"execution_id": "e1", "situacao": "succeeded", "automation_id": 7, "automacao": "F",
                                 "quando": AGORA, "falha": None}])
    avisos = Avisos([Pessoa(1, "a@x.com", False, frozenset({"termino"}))], ja={"fim:e1"})
    assert _detectar(leitor, avisos, _fila()[0]).execute() == {"ocorrencias": 0, "avisos": 0}
    assert avisos.gravadas == []


def test_ocorrencia_gravada_mesmo_sem_destinatario() -> None:
    leitor = Leitor(terminadas=[{"execution_id": "e1", "situacao": "succeeded", "automation_id": 7, "automacao": "F",
                                 "quando": AGORA, "falha": None}])
    avisos = Avisos([])
    assert _detectar(leitor, avisos, _fila()[0]).execute() == {"ocorrencias": 1, "avisos": 0}
    assert avisos.gravadas == [("fim:e1", [])]


def test_permissao_consultada_uma_vez_por_pessoa_e_automacao() -> None:
    fins = [{"execution_id": f"e{i}", "situacao": "succeeded", "automation_id": 7, "automacao": "F", "quando": AGORA,
             "falha": None} for i in range(3)]
    consultas: list[tuple[str, int]] = []

    def pode(usuario, automacao):
        consultas.append((usuario, automacao))
        return False

    avisos = Avisos([Pessoa(1, "a@x.com", False, frozenset({"termino"}))])
    assert _detectar(Leitor(terminadas=fins), avisos, _fila()[0], pode).execute() == {"ocorrencias": 3, "avisos": 0}
    assert consultas == [("usuario-1", 7)]


def test_maquina_offline_le_a_fila_e_os_sinais_so_se_algum_gestor_quer() -> None:
    sinal = AGORA - timedelta(minutes=2)
    leitor = Leitor(sinais={"m1": sinal})
    ver, chamadas = _fila(maquinas=[{"id": "m1", "nome": "FOLHA-01", "online": False},
                                    {"id": "m2", "nome": None, "online": False},
                                    {"id": "m3", "nome": "OK", "online": True}])
    so_operador = Avisos([Pessoa(1, "op@x.com", False, frozenset({"maquina_offline"}))])
    assert _detectar(leitor, so_operador, ver).execute() == {"ocorrencias": 0, "avisos": 0} and chamadas == []
    gestor = Avisos([Pessoa(2, "g@x.com", True, frozenset({"maquina_offline"}))])
    assert _detectar(leitor, gestor, ver).execute() == {"ocorrencias": 1, "avisos": 1}
    assert gestor.gravadas == [(f"offline:m1:{sinal.isoformat()}", [(2, "g@x.com")])] and chamadas == [AGORA]


def test_fila_parada_uma_por_tempo_escolhido() -> None:
    hora = (AGORA - timedelta(hours=1)).isoformat()
    ver, chamadas = _fila(jobs=[{"enfileirado_em": hora}, {"enfileirado_em": (AGORA - timedelta(minutes=5)).isoformat()}])
    avisos = Avisos([Pessoa(1, "a@x.com", True, frozenset({"fila_parada"}), 30),
                     Pessoa(2, "b@x.com", True, frozenset({"fila_parada"}), 45),
                     Pessoa(3, "c@x.com", True, frozenset({"fila_parada"}), 90),
                     Pessoa(4, "d@x.com", False, frozenset({"erro"}), 15)])
    leitor = Leitor(ultimo_inicio=AGORA - timedelta(hours=2))
    assert _detectar(leitor, avisos, ver).execute() == {"ocorrencias": 2, "avisos": 2}
    assert avisos.gravadas == [(f"fila_parada:{hora}:30", [(1, "a@x.com")]), (f"fila_parada:{hora}:45", [(2, "b@x.com")])]
    assert leitor.sinais_lidos == 0 and chamadas == [AGORA]


def test_fila_parada_respeita_o_ultimo_inicio() -> None:
    ver, _ = _fila(jobs=[{"enfileirado_em": (AGORA - timedelta(hours=1)).isoformat()}])
    avisos = Avisos([Pessoa(1, "a@x.com", True, frozenset({"fila_parada"}), 30)])
    leitor = Leitor(ultimo_inicio=AGORA - timedelta(minutes=10))
    assert _detectar(leitor, avisos, ver).execute() == {"ocorrencias": 0, "avisos": 0}


def test_commit_uma_vez() -> None:
    tx = Tx()
    DetectarOcorrencias(Leitor(), Avisos([]), _fila()[0], lambda u, a: True, tx, agora=lambda: AGORA).execute()
    assert tx.vezes == 1
