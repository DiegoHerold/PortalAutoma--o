"""Imagem de um passo: conferir, gerar as três medidas e guardar no Storage.

Vale para os dois modos: no direto a automação manda a imagem pela API; no modo agente o
Agent manda o arquivo ``passos/<imagem_id>.jpg`` e o Portal registra a imagem quando o
artefato termina de subir.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from modules.telemetry.domain.imagens import BUCKET, TAMANHOS, ImagemInvalida, chave_no_storage, id_valido


class RegistrarImagemDePasso:
    def __init__(self, contextos: Any, imagens: Any, guardar: Any, processar: Callable[[bytes], Any],
                 transaction: Any, avisar: Callable[[str], None]) -> None:
        self.contextos = contextos
        self.imagens = imagens
        self.guardar = guardar
        self.processar = processar
        self.transaction = transaction
        self.avisar = avisar

    def execute(self, *, attempt_id: str, imagem_id: str, conteudo: bytes, origem: str) -> dict[str, Any]:
        if not id_valido(imagem_id):
            raise ImagemInvalida(422, "imagem_id inválido")
        contexto = self.contextos.get_context(attempt_id)
        if contexto is None:
            raise ImagemInvalida(404, "tentativa não encontrada")
        if self.imagens.obter(attempt_id, imagem_id) is not None:
            return {"imagem_id": imagem_id, "repetida": True}
        try:
            processada = self.processar(conteudo)
        except ImagemInvalida as exc:
            # Fica o registro da recusa (sem bytes): a tela diz por que o passo está sem imagem.
            self.imagens.adicionar(
                id=f"stp_{uuid4().hex}", imagem_id=imagem_id, execution_id=contexto.execution_id,
                task_execution_id=contexto.task_execution_id, execution_attempt_id=attempt_id,
                automation_id=self.imagens.automation_id_da_tarefa(contexto.task_execution_id), origem=origem,
                bytes=len(conteudo), status="recusada", motivo_recusa=exc.motivo[:300])
            self.transaction.commit()
            raise
        guardados = {
            tamanho: self.guardar.execute(
                bucket=BUCKET, object_key=chave_no_storage(contexto.execution_id, attempt_id, imagem_id, tamanho),
                conteudo=processada.versoes[tamanho], content_type="image/jpeg")
            for tamanho in TAMANHOS
        }
        nova = self.imagens.adicionar(
            id=f"stp_{uuid4().hex}", imagem_id=imagem_id, execution_id=contexto.execution_id,
            task_execution_id=contexto.task_execution_id, execution_attempt_id=attempt_id,
            automation_id=self.imagens.automation_id_da_tarefa(contexto.task_execution_id), origem=origem,
            cheia_id=guardados["cheia"].id, media_id=guardados["media"].id, miniatura_id=guardados["miniatura"].id,
            largura=processada.largura, altura=processada.altura, bytes=len(conteudo),
            sha256=guardados["cheia"].sha256, status="pronta")
        self.transaction.commit()
        if nova:
            self.avisar(contexto.execution_id)
        return {"imagem_id": imagem_id, "repetida": not nova}
