from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.models.accounting import AuditLog
from app.models.identity import Role, User
from app.models.stock import Warehouse
from app.schemas.users import UserCreate, UserUpdate


def _load_roles(db: Session, role_names: list[str]) -> list[Role]:
    roles = list(db.scalars(select(Role).where(Role.name.in_(role_names))).all())
    found = {role.name for role in roles}
    missing = sorted(set(role_names) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown roles: {', '.join(missing)}")
    return roles


def _load_warehouses(db: Session, warehouse_ids: list[int]) -> list[Warehouse]:
    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids))).all()) if warehouse_ids else []
    found = {warehouse.id for warehouse in warehouses}
    missing = sorted(set(warehouse_ids) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown warehouses: {', '.join(map(str, missing))}")
    return warehouses


def _validate_logistics_assignment(roles: list[Role], warehouses: list[Warehouse]) -> None:
    if not any(role.name == "logist" for role in roles):
        return
    if len(roles) != 1:
        raise HTTPException(status_code=422, detail="Logistics role cannot be combined with other roles")
    if not warehouses:
        raise HTTPException(status_code=422, detail="Logistics user requires at least one warehouse")


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)).all())


def list_users(db: Session, *, skip: int = 0, limit: int = 100) -> list[User]:
    stmt = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.warehouses))
        .order_by(User.username)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def create_user(db: Session, payload: UserCreate) -> User:
    roles = _load_roles(db, payload.role_names)
    warehouses = _load_warehouses(db, payload.warehouse_ids)
    _validate_logistics_assignment(roles, warehouses)
    user = User(
        username=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_active=payload.is_active,
        roles=roles,
        warehouses=warehouses,
    )
    db.add(user)
    try:
        db.flush()
        db.add(AuditLog(entity_type="user", entity_id=str(user.id), action="create", details=f"roles={','.join(payload.role_names)}"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User email already exists") from exc
    db.refresh(user)
    return user


def update_user(db: Session, user_id: int, payload: UserUpdate, *, current_user_id: int) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles), selectinload(User.warehouses))
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    values = payload.model_dump(exclude_unset=True)
    if values.get("is_active") is False and user.id == current_user_id:
        raise HTTPException(status_code=409, detail="Current user cannot deactivate own account")
    if "email" in values:
        user.username = values["email"]
    if "full_name" in values:
        user.full_name = values["full_name"]
    if "is_active" in values:
        user.is_active = values["is_active"]
    if values.get("password"):
        user.hashed_password = hash_password(values["password"])
    next_roles = user.roles
    if "role_names" in values and values["role_names"] is not None:
        next_roles = _load_roles(db, values["role_names"])
    next_warehouses = user.warehouses
    if "warehouse_ids" in values and values["warehouse_ids"] is not None:
        next_warehouses = _load_warehouses(db, values["warehouse_ids"])
    _validate_logistics_assignment(next_roles, next_warehouses)
    user.roles = next_roles
    user.warehouses = next_warehouses
    try:
        if values:
            db.add(AuditLog(entity_type="user", entity_id=str(user.id), action="update", details=",".join(sorted(values.keys()))))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User email already exists") from exc
    db.refresh(user)
    return user
