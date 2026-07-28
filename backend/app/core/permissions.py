from typing import Any

from modules.access.domain import RoleSlug


def is_admin(user: Any) -> bool:
    return bool(getattr(user, "role", None) and user.role.slug == RoleSlug.ADMIN.value)


def can_access_category(
    user: Any,
    category_id: int,
    action: str,
    permissions: list[Any],
) -> bool:
    if is_admin(user):
        return True

    for permission in permissions:
        if permission.category_id == category_id and getattr(permission, action, False):
            return True
    return False
