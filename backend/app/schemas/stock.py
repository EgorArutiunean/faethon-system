from decimal import Decimal

from app.schemas.common import Timestamped


class StockBalanceRead(Timestamped):
    id: int
    product_id: int
    product_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    quantity: Decimal


class StockMovementRead(Timestamped):
    id: int
    product_id: int
    product_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    document_id: int | None
    document_number: str | None = None
    movement_type: str | None = None
    quantity_delta: Decimal
    reason: str | None
