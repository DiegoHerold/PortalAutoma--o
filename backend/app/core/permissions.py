from app.core.constants import GlobalRoleSlug
from app.models.user import User
from app.models.user_category_permission import UserCategoryPermission


def is_admin(user: User) -> bool:
    return bool(user.role and user.role.slug == GlobalRoleSlug.ADMIN)


def can_access_category(
    user: User,
    category_id: int,
    action: str,
    permissions: list[UserCategoryPermission],
) -> bool:
    if is_admin(user):
        return True

    for permission in permissions:
        if permission.category_id == category_id and getattr(permission, action, False):
            return True
    return False
