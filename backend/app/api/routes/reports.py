from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.schemas.reports import (
    CashBookReport,
    DocumentsRegisterReport,
    PartnerDebtsReport,
    StockBalancesReport,
    StockMovementsReport,
)
from app.services import export_service, reports_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _export_response(report_key: str, report, export_format: str, filters: dict[str, object]) -> Response:
    try:
        exported = export_service.export_report(report_key, report, export_format, filters)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )


@router.get("/stock-balances", response_model=StockBalancesReport, dependencies=[Depends(require_permission("reports.read"))])
def stock_balances(
    warehouse_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    return reports_service.stock_balances_report(db, warehouse_id=warehouse_id, product_id=product_id, search=search)


@router.get("/stock-balances/export", dependencies=[Depends(require_permission("reports.read"))])
def export_stock_balances(
    format: str = Query(default="xlsx"),
    warehouse_id: int | None = None,
    product_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    filters = {"warehouse_id": warehouse_id, "product_id": product_id, "search": search}
    report = reports_service.stock_balances_report(db, **filters)
    return _export_response("stock-balances", report, format, filters)


@router.get("/stock-movements", response_model=StockMovementsReport, dependencies=[Depends(require_permission("reports.read"))])
def stock_movements(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    document_id: int | None = None,
    db: Session = Depends(get_db),
):
    return reports_service.stock_movements_report(
        db,
        date_from=date_from,
        date_to=date_to,
        warehouse_id=warehouse_id,
        product_id=product_id,
        document_id=document_id,
    )


@router.get("/stock-movements/export", dependencies=[Depends(require_permission("reports.read"))])
def export_stock_movements(
    format: str = Query(default="xlsx"),
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    document_id: int | None = None,
    db: Session = Depends(get_db),
):
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "document_id": document_id,
    }
    report = reports_service.stock_movements_report(db, **filters)
    return _export_response("stock-movements", report, format, filters)


@router.get("/partner-debts", response_model=PartnerDebtsReport, dependencies=[Depends(require_permission("reports.read"))])
def partner_debts(
    partner_id: int | None = None,
    partner_type: str | None = None,
    only_with_balance: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return reports_service.partner_debts_report(db, partner_id=partner_id, partner_type=partner_type, only_with_balance=only_with_balance)


@router.get("/partner-debts/export", dependencies=[Depends(require_permission("reports.read"))])
def export_partner_debts(
    format: str = Query(default="xlsx"),
    partner_id: int | None = None,
    partner_type: str | None = None,
    only_with_balance: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    filters = {"partner_id": partner_id, "partner_type": partner_type, "only_with_balance": only_with_balance}
    report = reports_service.partner_debts_report(db, **filters)
    return _export_response("partner-debts", report, format, filters)


@router.get("/cash-book", response_model=CashBookReport, dependencies=[Depends(require_permission("reports.read"))])
def cash_book(
    date_from: date | None = None,
    date_to: date | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return reports_service.cash_book_report(
        db,
        date_from=date_from,
        date_to=date_to,
        operation_type=operation_type,
        status=status,
    )


@router.get("/cash-book/export", dependencies=[Depends(require_permission("reports.read"))])
def export_cash_book(
    format: str = Query(default="xlsx"),
    date_from: date | None = None,
    date_to: date | None = None,
    operation_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "operation_type": operation_type,
        "status": status,
    }
    report = reports_service.cash_book_report(db, **filters)
    return _export_response("cash-book", report, format, filters)


@router.get("/documents-register", response_model=DocumentsRegisterReport, dependencies=[Depends(require_permission("reports.read"))])
def documents_register(
    date_from: date | None = None,
    date_to: date | None = None,
    document_type: str | None = None,
    status: str | None = None,
    partner_id: int | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
):
    return reports_service.documents_register_report(
        db,
        date_from=date_from,
        date_to=date_to,
        document_type=document_type,
        status=status,
        partner_id=partner_id,
        warehouse_id=warehouse_id,
    )


@router.get("/documents-register/export", dependencies=[Depends(require_permission("reports.read"))])
def export_documents_register(
    format: str = Query(default="xlsx"),
    date_from: date | None = None,
    date_to: date | None = None,
    document_type: str | None = None,
    status: str | None = None,
    partner_id: int | None = None,
    warehouse_id: int | None = None,
    db: Session = Depends(get_db),
):
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "document_type": document_type,
        "status": status,
        "partner_id": partner_id,
        "warehouse_id": warehouse_id,
    }
    report = reports_service.documents_register_report(db, **filters)
    return _export_response("documents-register", report, format, filters)
