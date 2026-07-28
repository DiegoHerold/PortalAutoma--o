from datetime import datetime

from pydantic import BaseModel


class GithubIntegrationRead(BaseModel):
    id: int
    installation_id: int
    account_login: str
    account_type: str
    connected_at: datetime | None
    suspended_at: datetime | None

    class Config:
        from_attributes = True


class GithubConnectResponse(BaseModel):
    install_url: str


class GithubRepositoryRead(BaseModel):
    id: int
    owner: str
    name: str
    full_name: str
    default_branch: str
    private: bool


class GithubDiscoverRequest(BaseModel):
    owner: str
    repository: str
    branch: str


class GithubImportRequest(BaseModel):
    owner: str
    repository: str
    branch: str
    manifest_paths: list[str]
