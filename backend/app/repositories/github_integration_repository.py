from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.github_integration import GithubIntegration


class GithubIntegrationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[GithubIntegration]:
        return list(self.db.scalars(select(GithubIntegration).order_by(GithubIntegration.account_login)).all())

    def get(self, integration_id: int) -> GithubIntegration | None:
        return self.db.get(GithubIntegration, integration_id)

    def get_by_installation_id(self, installation_id: int) -> GithubIntegration | None:
        return self.db.scalar(
            select(GithubIntegration).where(GithubIntegration.installation_id == installation_id)
        )

    def create(self, integration: GithubIntegration) -> GithubIntegration:
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def update(self, integration: GithubIntegration) -> GithubIntegration:
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def delete(self, integration: GithubIntegration) -> None:
        self.db.delete(integration)
        self.db.commit()
