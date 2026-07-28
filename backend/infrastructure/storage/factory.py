from functools import lru_cache

from infrastructure.config import get_settings
from infrastructure.storage.base import PackageStorage


@lru_cache
def get_package_storage() -> PackageStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from infrastructure.storage.s3_storage import S3PackageStorage

        return S3PackageStorage()
    from infrastructure.storage.local_storage import LocalPackageStorage

    return LocalPackageStorage()

