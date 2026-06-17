from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.identity import User
from app.schemas.users import RoleRead, UserCreate, UserRead, UserUpdate
from app.services import users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead], dependencies=[Depends(require_permission("users.manage"))])
def list_users(db: Session = Depends(get_db), skip: int = 0, limit: int = Query(default=100, le=500)):
    return users_service.list_users(db, skip=skip, limit=limit)


@router.post("", response_model=UserRead, status_code=201, dependencies=[Depends(require_permission("users.manage"))])
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return users_service.create_user(db, payload)


@router.patch("/{user_id}", response_model=UserRead, dependencies=[Depends(require_permission("users.manage"))])
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return users_service.update_user(db, user_id, payload, current_user_id=current_user.id)


@router.get("/roles", response_model=list[RoleRead], dependencies=[Depends(require_permission("users.manage"))])
def list_roles(db: Session = Depends(get_db)):
    return users_service.list_roles(db)
