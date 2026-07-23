from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import User
from app.models.user_category_permission import UserCategoryPermission


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                joinedload(User.category_permissions).joinedload(UserCategoryPermission.category),
            )
            .where(User.email == email)
        )
        return self.db.scalar(stmt)

    def get(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(
                joinedload(User.role),
                joinedload(User.category_permissions).joinedload(UserCategoryPermission.category),
            )
            .where(User.id == user_id)
        )
        return self.db.scalar(stmt)

    def list_all(self) -> list[User]:
        stmt = select(User).options(joinedload(User.role)).order_by(User.name)
        return list(self.db.scalars(stmt).unique().all())

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    def get_permission(self, user_id: int, category_id: int) -> UserCategoryPermission | None:
        stmt = select(UserCategoryPermission).where(
            UserCategoryPermission.user_id == user_id,
            UserCategoryPermission.category_id == category_id,
        )
        return self.db.scalar(stmt)

    def create_permission(self, permission: UserCategoryPermission) -> UserCategoryPermission:
        self.db.add(permission)
        self.db.flush()
        return permission
