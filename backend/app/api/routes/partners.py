from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.partners import Partner
from app.schemas.partners import PartnerCreate, PartnerRead, PartnerUpdate
from app.schemas.payments import PartnerBalanceRead, PartnerStatementRow
from app.services import directory_service
from app.services.crud import CRUDService
from app.services import payments_service

router = APIRouter(prefix="/partners", tags=["partners"])
service = CRUDService[Partner, PartnerCreate, PartnerUpdate](Partner)


@router.get("", response_model=list[PartnerRead], dependencies=[Depends(require_permission("partners.read"))])
def list_partners(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    search: str | None = None,
    partner_type: str | None = None,
):
    from sqlalchemy import select
    stmt = select(Partner).offset(skip).limit(limit)
    if search:
        stmt = stmt.where(Partner.name.ilike(f"%{search}%"))
    if partner_type:
        stmt = stmt.where(Partner.partner_type == partner_type)
    return list(db.scalars(stmt).all())


@router.post("", response_model=PartnerRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permission("partners.create"))])
def create_partner(payload: PartnerCreate, db: Session = Depends(get_db)):
    return directory_service.create_partner(db, payload)


@router.get("/balances", response_model=list[PartnerBalanceRead], dependencies=[Depends(require_permission("partners.read"))])
def list_partner_balances(db: Session = Depends(get_db)):
    return payments_service.get_partner_balances(db)


@router.get("/{item_id}", response_model=PartnerRead, dependencies=[Depends(require_permission("partners.read"))])
def get_partner(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    return obj


@router.get("/{item_id}/balance", response_model=PartnerBalanceRead, dependencies=[Depends(require_permission("partners.read"))])
def get_partner_balance(item_id: int, db: Session = Depends(get_db)):
    return payments_service.get_partner_balance(db, item_id)


@router.get("/{item_id}/statement", response_model=list[PartnerStatementRow], dependencies=[Depends(require_permission("partners.read"))])
def get_partner_statement(item_id: int, db: Session = Depends(get_db)):
    return payments_service.get_partner_statement(db, item_id)


@router.patch("/{item_id}", response_model=PartnerRead, dependencies=[Depends(require_permission("partners.update"))])
def update_partner(item_id: int, payload: PartnerUpdate, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    return directory_service.update_partner(db, obj, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_permission("partners.delete"))])
def delete_partner(item_id: int, db: Session = Depends(get_db)):
    obj = service.get(db, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Partner not found")
    directory_service.delete_partner(db, obj)
