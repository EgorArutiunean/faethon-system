from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.documents import Document, DocumentLine
from app.models.products import Product


MINIMUM_MARKUP_PERCENT = Decimal("10.00")
MONEY_QUANTUM = Decimal("0.01")


def _ranked_purchase_lines(product_ids: list[int]):
    return (
        select(
            DocumentLine.product_id.label("product_id"),
            DocumentLine.price.label("purchase_cost"),
            Document.id.label("document_id"),
            Document.number.label("document_number"),
            Document.document_date.label("document_date"),
            func.row_number()
            .over(
                partition_by=DocumentLine.product_id,
                order_by=(
                    Document.document_date.desc(),
                    Document.id.desc(),
                    DocumentLine.id.desc(),
                ),
            )
            .label("purchase_rank"),
        )
        .join(Document, Document.id == DocumentLine.document_id)
        .where(
            Document.document_type == Document.TYPE_INCOMING,
            Document.status == Document.STATUS_POSTED,
            DocumentLine.product_id.in_(product_ids),
        )
        .subquery()
    )


def _pricing_values(sale_price: Decimal | None, purchase_cost: Decimal | None) -> dict:
    if purchase_cost is None:
        return {
            "markup_percent": None,
            "minimum_sale_price": None,
            "price_review_required": False,
        }
    minimum_sale_price = (purchase_cost * (Decimal("1") + MINIMUM_MARKUP_PERCENT / Decimal("100"))).quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    if purchase_cost <= 0:
        return {
            "markup_percent": None,
            "minimum_sale_price": minimum_sale_price,
            "price_review_required": False,
        }
    if sale_price is None:
        return {
            "markup_percent": None,
            "minimum_sale_price": minimum_sale_price,
            "price_review_required": True,
        }
    markup_percent = ((sale_price - purchase_cost) / purchase_cost * Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return {
        "markup_percent": markup_percent,
        "minimum_sale_price": minimum_sale_price,
        "price_review_required": markup_percent < MINIMUM_MARKUP_PERCENT,
    }


def attach_product_pricing(db: Session, products: list[Product]) -> list[Product]:
    if not products:
        return products
    product_ids = [product.id for product in products]
    ranked = _ranked_purchase_lines(product_ids)
    rows = db.execute(
        select(ranked).where(
            ranked.c.purchase_rank == 1,
            ranked.c.product_id.in_(product_ids),
        )
    ).mappings()
    latest_by_product = {row["product_id"]: row for row in rows}
    for product in products:
        latest = latest_by_product.get(product.id)
        purchase_cost = latest["purchase_cost"] if latest else None
        product.latest_purchase_cost = purchase_cost
        product.latest_purchase_document_id = latest["document_id"] if latest else None
        product.latest_purchase_document_number = latest["document_number"] if latest else None
        product.latest_purchase_date = latest["document_date"] if latest else None
        for name, value in _pricing_values(product.base_price, purchase_cost).items():
            setattr(product, name, value)
    return products


def attach_single_product_pricing(db: Session, product: Product) -> Product:
    return attach_product_pricing(db, [product])[0]
