from __future__ import annotations

from modules.catalog.application.dto import RuntimeDTO, RuntimeVersionDTO
from modules.catalog.application.use_cases.runtimes import ListRuntimeVersions
from modules.catalog.domain.errors import CatalogValidationError
from modules.storage.domain.upload_session import UploadSession, UploadSessionStatus
from modules.storage.infrastructure.adapters.package_storage_adapter import ApiTemporaryUrlProvider


class RuntimeRepositoryStub:
    def __init__(self) -> None:
        self.runtime = RuntimeDTO(
            id="runtime-1",
            key="python-desktop",
            name="Python Desktop",
            description=None,
            status="active",
        )
        self.versions = [
            RuntimeVersionDTO(
                id="rv-1",
                runtime_id="runtime-1",
                version="1.0.0",
                operating_system="windows",
                architecture="x64",
                status="published",
                minimum_agent_version="1.4.0",
                supported_entrypoints=["python-function"],
                supported_execution_modes=["background"],
                metadata={},
            )
        ]

    def get_runtime(self, runtime_id: str) -> RuntimeDTO | None:
        return self.runtime if runtime_id == self.runtime.id else None

    def list_runtime_versions(self, runtime_id: str) -> list[RuntimeVersionDTO]:
        return self.versions if runtime_id == self.runtime.id else []


def test_list_runtime_versions_returns_versions_for_runtime() -> None:
    result = ListRuntimeVersions(RuntimeRepositoryStub()).execute("runtime-1")

    assert len(result) == 1
    assert result[0].version == "1.0.0"
    assert result[0].minimum_agent_version == "1.4.0"


def test_list_runtime_versions_rejects_unknown_runtime() -> None:
    try:
        ListRuntimeVersions(RuntimeRepositoryStub()).execute("missing")
    except CatalogValidationError:
        return
    raise AssertionError("Unknown runtime should be rejected.")


def test_catalog_api_temporary_url_provider_uses_direct_api_upload_branch() -> None:
    provider = ApiTemporaryUrlProvider("/api/v1")
    upload_session = UploadSession(
        id="upload-1",
        stored_object_id="object-1",
        upload_url=None,
        status=UploadSessionStatus.INITIATED,
    )

    assert provider.create_upload_url(upload_session) is None
