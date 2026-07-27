from __future__ import annotations

from sqlalchemy.orm import Session

from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus
from modules.storage.infrastructure.orm.models import StoredObjectRecord, UploadSessionRecord


class SqlAlchemyStoredObjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, stored_object: StoredObject) -> StoredObject:
        row = StoredObjectRecord(
            id=stored_object.id,
            bucket=stored_object.bucket,
            object_key=stored_object.object_key,
            content_type=stored_object.content_type,
            size_bytes=stored_object.size_bytes,
            sha256=stored_object.sha256,
            etag=stored_object.etag,
            provider=stored_object.provider,
            status=stored_object.status.value,
            verified_at=stored_object.verified_at,
            deleted_at=stored_object.deleted_at,
        )
        self.db.add(row)
        self.db.flush()
        return self._to_domain(row)

    def get(self, stored_object_id: str) -> StoredObject | None:
        row = self.db.get(StoredObjectRecord, stored_object_id)
        return self._to_domain(row) if row else None

    def update(self, stored_object: StoredObject) -> StoredObject:
        row = self.db.get(StoredObjectRecord, stored_object.id)
        if row is None:
            raise ValueError("StoredObject not found.")
        row.bucket = stored_object.bucket
        row.object_key = stored_object.object_key
        row.content_type = stored_object.content_type
        row.size_bytes = stored_object.size_bytes
        row.sha256 = stored_object.sha256
        row.etag = stored_object.etag
        row.provider = stored_object.provider
        row.status = stored_object.status.value
        row.verified_at = stored_object.verified_at
        row.deleted_at = stored_object.deleted_at
        self.db.add(row)
        self.db.flush()
        return self._to_domain(row)

    def _to_domain(self, row: StoredObjectRecord) -> StoredObject:
        return StoredObject(
            id=row.id,
            bucket=row.bucket,
            object_key=row.object_key,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            etag=row.etag,
            provider=row.provider,
            status=StoredObjectStatus(row.status),
            created_at=row.created_at,
            verified_at=row.verified_at,
            deleted_at=row.deleted_at,
        )


class SqlAlchemyUploadSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, upload_session: UploadSession) -> UploadSession:
        row = UploadSessionRecord(
            id=upload_session.id,
            stored_object_id=upload_session.stored_object_id,
            upload_url=upload_session.upload_url,
            status=upload_session.status.value,
            expected_size_bytes=upload_session.expected_size_bytes,
            expected_sha256=upload_session.expected_sha256,
            created_by=upload_session.created_by,
            expires_at=upload_session.expires_at,
            completed_at=upload_session.completed_at,
            aborted_at=upload_session.aborted_at,
        )
        self.db.add(row)
        self.db.flush()
        return self._to_domain(row)

    def get(self, upload_session_id: str) -> UploadSession | None:
        row = self.db.get(UploadSessionRecord, upload_session_id)
        return self._to_domain(row) if row else None

    def update(self, upload_session: UploadSession) -> UploadSession:
        row = self.db.get(UploadSessionRecord, upload_session.id)
        if row is None:
            raise ValueError("UploadSession not found.")
        row.upload_url = upload_session.upload_url
        row.status = upload_session.status.value
        row.expected_size_bytes = upload_session.expected_size_bytes
        row.expected_sha256 = upload_session.expected_sha256
        row.completed_at = upload_session.completed_at
        row.aborted_at = upload_session.aborted_at
        self.db.add(row)
        self.db.flush()
        return self._to_domain(row)

    def _to_domain(self, row: UploadSessionRecord) -> UploadSession:
        return UploadSession(
            id=row.id,
            stored_object_id=row.stored_object_id,
            upload_url=row.upload_url,
            status=UploadSessionStatus(row.status),
            expected_size_bytes=row.expected_size_bytes,
            expected_sha256=row.expected_sha256,
            created_by=row.created_by,
            created_at=row.created_at,
            expires_at=row.expires_at,
            completed_at=row.completed_at,
            aborted_at=row.aborted_at,
        )
