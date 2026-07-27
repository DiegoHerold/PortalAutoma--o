from __future__ import annotations

from modules.storage.domain.stored_object import StoredObject, StoredObjectStatus


def test_stored_object_rejects_unsafe_object_key() -> None:
    try:
        StoredObject(
            id="1",
            bucket="packages",
            object_key="../package.zip",
            content_type="application/zip",
            size_bytes=10,
            sha256=None,
            etag=None,
            provider="local",
            status=StoredObjectStatus.PENDING,
        )
    except ValueError:
        return
    raise AssertionError("unsafe object_key should be rejected")
