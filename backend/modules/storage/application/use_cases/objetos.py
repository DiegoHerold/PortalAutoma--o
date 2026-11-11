"""Guardar e ler objetos pequenos (imagens dos passos) pelo Storage, dono dos objetos.

Outros contextos chamam estes casos de uso; nunca escrevem em ``stored_objects`` nem no
armazenamento diretamente. Nada aqui gera URL pública: quem lê é a API, depois de
conferir a permissão.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from modules.storage.domain.errors import ArtifactNotFound
from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus


class GuardarObjeto:
    def __init__(self, object_storage: Any, stored_objects: Any) -> None:
        self.object_storage = object_storage
        self.stored_objects = stored_objects

    def execute(self, *, bucket: str, object_key: str, conteudo: bytes, content_type: str) -> StoredObject:
        caminho: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix="objeto_", delete=False) as tmp:
                tmp.write(conteudo)
                caminho = Path(tmp.name)
            gravado = self.object_storage.put_file(bucket, object_key, caminho, content_type)
        finally:
            if caminho is not None and caminho.exists():
                caminho.unlink()
        return self.stored_objects.add(StoredObject(
            id=str(uuid4()), bucket=gravado.bucket, object_key=gravado.object_key, content_type=content_type,
            size_bytes=len(conteudo), sha256=hashlib.sha256(conteudo).hexdigest(), etag=None,
            provider=gravado.provider, status=StoredObjectStatus.VERIFIED))


class LerObjeto:
    def __init__(self, object_storage: Any, stored_objects: Any) -> None:
        self.object_storage = object_storage
        self.stored_objects = stored_objects

    def execute(self, stored_object_id: str) -> tuple[bytes, str]:
        objeto = self.stored_objects.get(stored_object_id)
        if objeto is None or objeto.status == StoredObjectStatus.DELETED:
            raise ArtifactNotFound("Objeto não encontrado.")
        return self.object_storage.read_bytes(objeto.bucket, objeto.object_key), objeto.content_type


class ApagarObjeto:
    """Apaga os bytes e marca o objeto como apagado (retenção). Apagar de novo não faz nada."""

    def __init__(self, object_storage: Any, stored_objects: Any) -> None:
        self.object_storage = object_storage
        self.stored_objects = stored_objects

    def execute(self, stored_object_id: str) -> bool:
        objeto = self.stored_objects.get(stored_object_id)
        if objeto is None or objeto.status == StoredObjectStatus.DELETED:
            return False
        self.object_storage.delete_object(objeto.bucket, objeto.object_key)
        self.stored_objects.update(replace(objeto, status=StoredObjectStatus.DELETED, deleted_at=datetime.now(UTC)))
        return True


BUCKET_ARQUIVOS = "arquivos-entregues"
NOME_SEGURO = re.compile(r"[^\w.\- ()]+", re.UNICODE)


def nome_seguro(nome: str) -> str:
    """Só o nome do arquivo (sem pasta), sem caracteres que confundem o sistema de arquivos."""
    base = Path(str(nome).replace("\\", "/")).name.strip()
    base = NOME_SEGURO.sub("_", base)[:200].strip(" .")
    return base or "arquivo"


class GuardarArquivoEntregue:
    """Arquivo que a automação entregou (planilha, TXT...): vira um artefato da execução (Fase 8).

    Os bytes vão para o armazenamento; o registro liga ao job e à tentativa. Ninguém baixa sem
    passar pela API, que confere a permissão e audita."""

    def __init__(self, object_storage: Any, stored_objects: Any, artifacts: Any) -> None:
        self.object_storage = object_storage
        self.stored_objects = stored_objects
        self.artifacts = artifacts

    def execute(self, *, execution_id: str, task_execution_id: str, execution_attempt_id: str, caminho: Path,
                nome: str, content_type: str, sha256: str, tamanho: int, metadados: dict[str, Any]) -> Any:
        from modules.storage.application.dto import ArtifactDTO
        from modules.storage.domain.states import ArtifactStatus

        nome = nome_seguro(nome)
        artefato_id = f"art_{uuid4().hex}"
        chave = f"{execution_id}/{execution_attempt_id}/{artefato_id}/{nome}"
        gravado = self.object_storage.put_file(BUCKET_ARQUIVOS, chave, caminho, content_type)
        objeto = self.stored_objects.add(StoredObject(
            id=str(uuid4()), bucket=gravado.bucket, object_key=gravado.object_key, content_type=content_type,
            size_bytes=tamanho, sha256=sha256, etag=None, provider=gravado.provider, status=StoredObjectStatus.VERIFIED))
        agora = datetime.now(UTC)
        return self.artifacts.add(ArtifactDTO(
            id=artefato_id, execution_id=execution_id, task_execution_id=task_execution_id,
            execution_attempt_id=execution_attempt_id, name=nome, content_type=content_type,
            status=ArtifactStatus.AVAILABLE.value, stored_object_id=objeto.id, upload_session_id=None,
            size_bytes=tamanho, sha256=sha256, metadata={"origem": "direto", **metadados},
            created_at=agora, uploaded_at=agora))
