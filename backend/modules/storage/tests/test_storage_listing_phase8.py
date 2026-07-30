from __future__ import annotations

from modules.storage.application.dto import ArtifactDTO
from modules.storage.application.use_cases.artifacts import ListArtifacts
from modules.storage.api.routes import _system_limit_bytes


class ArtifactRepositoryStub:
    def __init__(self) -> None:
        self.received: dict[str, object] | None = None

    def list(self, **kwargs) -> list[ArtifactDTO]:
        self.received = kwargs
        return [
            ArtifactDTO(
                id="art-1",
                execution_id="exe-1",
                task_execution_id="task-1",
                execution_attempt_id="att-1",
                name="report.csv",
                content_type="text/csv",
                status="available",
                stored_object_id="obj-1",
                upload_session_id="upl-1",
            )
        ]


def test_list_artifacts_forwards_filters_and_pagination() -> None:
    repository = ArtifactRepositoryStub()

    artifacts = ListArtifacts(repository).execute(
        execution_id="exe-1",
        status="available",
        search="report",
        limit=25,
        offset=50,
    )

    assert artifacts[0].name == "report.csv"
    assert repository.received == {
        "execution_id": "exe-1",
        "status": "available",
        "search": "report",
        "limit": 25,
        "offset": 50,
    }
