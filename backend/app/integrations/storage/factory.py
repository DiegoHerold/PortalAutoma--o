from functools import lru_cache

from app.core.config import get_settings
from app.integrations.storage.base import PackageStorage


@lru_cache
def get_package_storage() -> PackageStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.integrations.storage.s3_storage import S3PackageStorage

        return S3PackageStorage()
    from app.integrations.storage.local_storage import LocalPackageStorage

    return LocalPackageStorage()
