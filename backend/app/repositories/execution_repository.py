from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.execution import Execution
from app.models.log import ExecutionLog


class ExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Execution]:
        stmt = (
            select(Execution)
            .options(joinedload(Execution.logs))
            .order_by(Execution.created_at.desc())
        )
        return list(self.db.scalars(stmt).unique().all())

    def get(self, execution_id: int) -> Execution | None:
        stmt = (
            select(Execution)
            .options(joinedload(Execution.logs))
            .where(Execution.id == execution_id)
        )
        return self.db.scalar(stmt)

    def create(self, execution: Execution) -> Execution:
        self.db.add(execution)
        self.db.flush()
        return execution

    def create_log(self, log: ExecutionLog) -> ExecutionLog:
        self.db.add(log)
        self.db.flush()
        return log
