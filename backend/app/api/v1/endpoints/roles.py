from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user
from app.schemas.role import RoleRead
from app.services.role_service import RoleService

router = APIRouter()


@router.get("")
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[RoleRead]:
    return RoleService(db).list_roles()
