from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, cash, documents, health, imports, partners, payments, products, reports, stock, warehouses
from app.core.config import get_settings
import app.db.base  # noqa: F401

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Service health checks"},
        {"name": "auth", "description": "Login and current user"},
        {"name": "products", "description": "Product catalog"},
        {"name": "partners", "description": "Customers, suppliers, and counterparties"},
        {"name": "warehouses", "description": "Warehouse directory"},
        {"name": "documents", "description": "Accounting documents; posting rules pending legacy confirmation"},
        {"name": "stock", "description": "Stock balances and movements"},
        {"name": "payments", "description": "Payments, partner balances, and debt statements"},
        {"name": "cash", "description": "Cash operations, cash balance, and cash book"},
        {"name": "reports", "description": "BuySell-like operational reports"},
        {"name": "import", "description": "CSV/XLSX import templates, dry-run validation, and apply"},
        {"name": "audit", "description": "Read-only operational audit log"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(products.router, prefix=settings.api_prefix)
app.include_router(partners.router, prefix=settings.api_prefix)
app.include_router(warehouses.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(stock.router, prefix=settings.api_prefix)
app.include_router(payments.router, prefix=settings.api_prefix)
app.include_router(cash.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(imports.router, prefix=settings.api_prefix)
app.include_router(audit.router, prefix=settings.api_prefix)
