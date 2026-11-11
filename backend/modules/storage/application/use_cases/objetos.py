"""Guardar e ler objetos pequenos (imagens dos passos) pelo Storage, dono dos objetos.

Outros contextos chamam estes casos de uso; nunca escrevem em ``stored_objects`` nem no
armazenamento diretamente. Nada aqui gera URL pública: quem lê é a API, depois de
conferir a permissão.
"""

from __future__ import annotations

import hashlib
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
