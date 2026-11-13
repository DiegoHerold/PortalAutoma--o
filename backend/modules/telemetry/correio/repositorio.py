"""E-mails, anexos e domínios permitidos (13/11/2026)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import String, cast, delete, func, or_, select, update
from sqlalchemy.orm import Session

from modules.telemetry.correio.correio import Contexto, Mensagem
from modules.telemetry.correio.modelos import EmailAnexoRecord, EmailDominioRecord, EmailRecord

_UNSET: Any = object()


class SqlAlchemyCorreio:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- domínios --------------------------------------------------------------------------------
    def dominios(self) -> list[str]:
        return list(self.db.scalars(select(EmailDominioRecord.dominio).order_by(EmailDominioRecord.dominio)))

    def adicionar_dominio(self, dominio: str, por: str | None, agora: datetime) -> None:
        if self.db.get(EmailDominioRecord, dominio) is None:
            self.db.add(EmailDominioRecord(dominio=dominio, criado_por=por, criado_em=agora))
            self.db.flush()

    def remover_dominio(self, dominio: str) -> None:
        self.db.execute(delete(EmailDominioRecord).where(EmailDominioRecord.dominio == dominio))
        self.db.flush()

    # -- e-mails ---------------------------------------------------------------------------------
    def criar(self, *, id: str, contexto: Contexto, mensagem: Mensagem, meio: str, situacao: str, motivo: str | None,
              chave: str | None, agora: datetime, guardar_anexos: bool, nomes_dos_anexos: list[str] | None = None) -> EmailRecord:
        registro = EmailRecord(id=id, origem=contexto.origem, tipo=contexto.tipo, automation_id=contexto.automation_id,
                               execution_id=contexto.execution_id, job_id=contexto.job_id, instancia_id=contexto.instancia_id,
                               criado_por=contexto.criado_por, para=mensagem.para, cc=mensagem.cc, cco=mensagem.cco,
                               assunto=mensagem.assunto, html=mensagem.html, texto=mensagem.texto, situacao=situacao,
                               motivo=motivo, meio=meio, tentativas=0, chave_idempotencia=chave, criado_em=agora)
        self.db.add(registro)
        self.db.flush()
        for nome, tipo, conteudo in mensagem.anexos:
            self.db.add(EmailAnexoRecord(id=f"ema_{uuid4().hex[:24]}", email_id=id, nome=nome, tipo=tipo, tamanho=len(conteudo),
                                         conteudo=conteudo if guardar_anexos else None))
        for nome in nomes_dos_anexos or []:
            self.db.add(EmailAnexoRecord(id=f"ema_{uuid4().hex[:24]}", email_id=id, nome=nome, tipo="application/octet-stream",
                                         tamanho=0, conteudo=None))
        self.db.flush()
        return registro

    def marcar(self, registro: EmailRecord, *, situacao: str | None = None, tentativas: int | None = None,
               motivo: Any = _UNSET, proxima: Any = _UNSET, enviado_em: datetime | None = None) -> None:
        if situacao is not None:
            registro.situacao = situacao
        if tentativas is not None:
            registro.tentativas = tentativas
        if motivo is not _UNSET:
            registro.motivo = motivo
        if proxima is not _UNSET:
            registro.proxima_tentativa_em = proxima
        if enviado_em is not None:
            registro.enviado_em = enviado_em
        self.db.flush()

    def email(self, email_id: str) -> EmailRecord | None:
        return self.db.get(EmailRecord, email_id)

    def anexos(self, email_id: str) -> list[EmailAnexoRecord]:
        return list(self.db.scalars(select(EmailAnexoRecord).where(EmailAnexoRecord.email_id == email_id).order_by(EmailAnexoRecord.nome)))

    def mensagem(self, registro: EmailRecord) -> Mensagem:
        return Mensagem(para=list(registro.para), cc=list(registro.cc or []), cco=list(registro.cco or []), assunto=registro.assunto,
                        html=registro.html, texto=registro.texto,
                        anexos=[(a.nome, a.tipo, a.conteudo) for a in self.anexos(registro.id) if a.conteudo is not None])

    def tem_conteudo(self, registro: EmailRecord) -> bool:
        return all(a.conteudo is not None for a in self.anexos(registro.id))

    def apagar_conteudo_dos_anexos(self, registro: EmailRecord) -> None:
        self.db.execute(update(EmailAnexoRecord).where(EmailAnexoRecord.email_id == registro.id).values(conteudo=None))
        self.db.flush()

    def por_chave(self, execution_id: str, chave: str) -> EmailRecord | None:
        return self.db.scalar(select(EmailRecord).where(EmailRecord.execution_id == execution_id,
                                                        EmailRecord.chave_idempotencia == chave).limit(1))

    def na_fila(self, agora: datetime, limite: int) -> list[EmailRecord]:
        return list(self.db.scalars(select(EmailRecord).where(
            EmailRecord.situacao == "na_fila",
            or_(EmailRecord.proxima_tentativa_em.is_(None), EmailRecord.proxima_tentativa_em <= agora))
            .order_by(EmailRecord.criado_em).limit(limite).with_for_update(skip_locked=True)))

    def lista(self, *, situacao: str | None, automation_id: int | None, busca: str | None, antes: datetime | None,
              limite: int) -> list[EmailRecord]:
        consulta = select(EmailRecord).order_by(EmailRecord.criado_em.desc()).limit(limite)
        if situacao:
            consulta = consulta.where(EmailRecord.situacao == situacao)
        if automation_id is not None:
            consulta = consulta.where(EmailRecord.automation_id == automation_id)
        if antes is not None:
            consulta = consulta.where(EmailRecord.criado_em < antes)
        if busca:
            termo = f"%{busca.lower()}%"
            consulta = consulta.where(or_(func.lower(EmailRecord.assunto).like(termo),
                                          func.lower(cast(EmailRecord.para, String)).like(termo)))
        return list(self.db.scalars(consulta))

    def contagem_por_situacao(self, desde: datetime) -> dict[str, int]:
        linhas = self.db.execute(select(EmailRecord.situacao, func.count()).where(EmailRecord.criado_em >= desde)
                                 .group_by(EmailRecord.situacao)).all()
        return {s: int(n) for s, n in linhas}

    def nomes_das_automacoes(self, ids: set[int]) -> dict[int, str]:
        from sqlalchemy import text

        if not ids:
            return {}
        return {int(i): n for i, n in self.db.execute(text("SELECT id, name FROM automations WHERE id = ANY(:i)"), {"i": list(ids)})}
