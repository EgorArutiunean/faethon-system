from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.partners import Partner
from app.schemas.partners import PartnerCreate, PartnerPage, PartnerRead, PartnerUpdate
from app.schemas.payments import PartnerBalanceRead, PartnerStatementRow
from app.services import directory_service, payments_service
from app.services.crud import CRUDService

router = APIRouter(prefix="/partners", tags=["partners"])
service = CRUDService[Partner, PartnerCreate, PartnerUpdate](Partner)


@router.get(
    "",
    response_model=list[PartnerRead],
    dependencies=[Depends(require_permission("partners.read"))],
)
def list_partners(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    search: str | None = None,
    partner_type: str | None = None,
):
    stmt = select(Partner).offset(skip).limit(limit)
    if search:
        stmt = stmt.where(Partner.name.ilike(f"%{search}%"))
    if partner_type:
        stmt = stmt.where(Partner.partner_type == partner_type)
    return list(db.scalars(stmt).all())


@router.get(
    "/page", response_model=PartnerPage, dependencies=[Depends(require_permission("partners.read"))]
)
def page_partners(
    db: Session = Depends(get_db),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    partner_type: str | None = None,
    sort_by: Literal["name", "code", "partner_type", "created_at", "is_active"] = "name",
    sort_order: Literal["asc", "desc"] = "asc",
):
    filters = []
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                Partner.name.ilike(pattern),
                Partner.code.ilike(pattern),
                Partner.phone.ilike(pattern),
            )
        )
    if partner_type:
        filters.append(Partner.partner_type == partner_type)
    total = db.scalar(select(func.count(Partner.id)).where(*filters)) or 0
    sort_column = getattr(Partner, sort_by)
    order = desc(sort_column) if sort_order == "desc" else asc(sort_column)
    stmt = select(Partner).where(*filters).order_by(order, Partner.id).offset(offset).limit(limit)
    return PartnerPage(items=list(db.scalars(stmt).all()), total=total, offset=offset, limit=limit)


@router.get(
    "/options",
    response_model=list[PartnerRead],
    dependencies=[Depends(require_permission("partners.read"))],
)
def partner_options(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    role: Literal["customer", "supplier"] | None = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    filters: list[ColumnElement[bool]] = [Partner.is_active.is_(True)]
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                Partner.name.ilike(pattern),
                Partner.code.ilike(pattern),
                Partner.phone.ilike(pattern),
            )
        )
    if role:
        filters.append(Partner.partner_type.in_((role, Partner.TYPE_BOTH)))
    stmt = select(Partner).where(*filters).order_by(Partner.name, Partner.id).limit(limit)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=PartnerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("partners.create"))],
)
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):
    return directory_service.create_partner(db, payload)


@router.get(
    "/balances",
    response_model=list[PartnerBalanceRead],
    dependencies=[Depends(require_permission("partners.read"))],
)
def list_partner_balances(
    db: Session = Depends(get_db),
    partner_ids: list[int] | None = Query(default=None),
):
    return payments_service.get_partner_balances(db, partner_ids=partner_ids)


@router.get(
    "/{item_id}",
    response_model=PartnerRead,
    dependencies=[Depends(require_permission("partners.read"))],
)
def get_partner(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    return obj


@router.get(
    "/{item_id}/balance",
    response_model=PartnerBalanceRead,
    dependencies=[Depends(require_permission("partners.read"))],
)
def get_partner_balance(item_id: int, db: Session = Depends(get_db)):
    return payments_service.get_partner_balance(db, item_id)


@router.get(
    "/{item_id}/statement",
    response_model=list[PartnerStatementRow],
    dependencies=[Depends(require_permission("partners.read"))],
)
def get_partner_statement(item_id: int, db: Session = Depends(get_db)):
    return payments_service.get_partner_statement(db, item_id)


@router.patch(
    "/{item_id}",
    response_model=PartnerRead,
    dependencies=[Depends(require_permission("partners.update"))],
)
def update_partner(item_id: int, payload: PartnerUpdate, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    return directory_service.update_partner(db, obj, payload)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("partners.delete"))],
)
def delete_partner(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    directory_service.delete_partner(db, obj)
