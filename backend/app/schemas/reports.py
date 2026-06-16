from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class StockBalancesReportRow(BaseModel):
    product_id: int
    product_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    quantity: Decimal


class StockBalancesReport(BaseModel):
    rows: list[StockBalancesReportRow]
    total_quantity: Decimal


class StockMovementsReportRow(BaseModel):
    id: int
    created_at: datetime
    product_id: int
    product_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    document_id: int | None = None
    document_number: str | None = None
    document_type: str | None = None
    status: str | None = None
    movement_type: str | None = None
    quantity_delta: Decimal


class StockMovementsReport(BaseModel):
    rows: list[StockMovementsReportRow]
    total_quantity: Decimal


class PartnerDebtsReportRow(BaseModel):
    partner_id: int
    partner_name: str
    partner_type: str
    balance: Decimal


class PartnerDebtsReport(BaseModel):
    rows: list[PartnerDebtsReportRow]
    total_partner_debt: Decimal


class CashBookReportRow(BaseModel):
    id: int
    operation_date: date
    operation_type: str
    status: str
    amount: Decimal
    partner_id: int | None = None
    partner_name: str | None = None
    payment_id: int | None = None
    document_id: int | None = None
    cash_balance: Decimal


class CashBookReport(BaseModel):
    rows: list[CashBookReportRow]
    cash_in_total: Decimal
    cash_out_total: Decimal
    cash_balance: Decimal


class DocumentsRegisterReportRow(BaseModel):
    id: int
    document_number: str | None = None
    document_date: date
    document_type: str
    status: str
    partner_id: int | None = None
    partner_name: str | None = None
    warehouse_id: int | None = None
    warehouse_name: str | None = None
    destination_warehouse_id: int | None = None
    destination_warehouse_name: str | None = None
    total_amount: Decimal


class DocumentsRegisterReport(BaseModel):
    rows: list[DocumentsRegisterReportRow]
    total_amount: Decimal
