# Project Status

## Current Phase

The application has a working Stock, Documents, Payments, Debts, Cash, Simple Auth, Reports, Export, Print Forms, and Import Lite core MVP.

As of 2026-06-16, the next delivery step is publication of this codebase to `EgorArutiunean/faethon-system` on GitHub. Live production deployment is intentionally deferred until server access and legacy data readiness are complete.

Implemented:

- product, partner, and warehouse directories;
- product category directory and product category assignment;
- document creation with generated numbers;
- document lines with quantity, price, and calculated totals;
- draft document header editing;
- draft document line deletion with total recalculation;
- draft document deletion;
- posted/cancelled document edit/delete protection;
- draft document posting;
- document cancellation;
- stock balances;
- stock movements;
- audit log entries for document actions;
- protected audit log API and frontend viewer for admin/accountability review;
- payment creation, posting, and cancellation;
- draft payment editing and deletion before posting;
- cash operation records linked to posted/cancelled payments;
- manual cash operations with `cash_in`, `cash_out`, and `correction` types;
- cash balance and cash book API;
- partner balances calculated from posted documents and posted payments;
- partner statement API and frontend view;
- frontend document list, document editor, stock balances, and stock movements views.
- frontend product category creation, editing, deletion for unused categories, and category selection in product cards.
- frontend payments list/form and partner balance/statement views;
- frontend cash balance, cash operation form, and cash book view.
- login with JWT access token;
- simple role and object/action permissions;
- demo users for admin, manager, cashier, and viewer roles;
- admin user management API and Settings UI for creating, activating/deactivating, password reset, and role assignment;
- frontend protected routes and permission-aware actions.
- reports API for stock balances, stock movements, partner debts, cash book, and documents register;
- frontend Reports page with tabs, filters, totals, loading/error/empty states, and `reports.read` access handling.
- XLSX/CSV export for core reports using the same filters as on-screen reports.
- frontend enum labels for core document, payment, cash, partner, movement, status, and Import Lite values.
- legacy-oriented HTML outgoing invoice print view with protected `documents.read` access, matched to the old program screenshot for releasing goods from own warehouse to a customer.
- PDF invoice export with embedded DejaVu font for readable Russian text, protected by `documents.read`, and available from the document editor.
- operator UX improvements for document editing, product search, current stock display, validations, confirmations, toasts, status badges, and basic table search/sort/pagination.
- CSV/XLSX Import Lite for products, partners, warehouses, opening stock, and opening partner balances with dry-run validation.
- inspected `E:\пример.xlsx` old price-list sample: `BuyData` has 353 product rows with columns `Склад`, `Код`, `Товар`, `Ед.`, `Кол-во`, purchase/rest/retail price fields; category-like values are embedded in the product name and need controlled import parsing rather than a hardcoded rule.
- business logic/CRUD audit for core entities;
- partner split into `customer`, `supplier`, and `both` with document/payment validation and UI filters.
- production deployment prep: `docker-compose.prod.yml`, production Dockerfiles, nginx SPA/API proxy config, env template, and PostgreSQL backup/restore scripts.
- production Docker/PostgreSQL smoke completed successfully on 2026-05-03.

## Local Runtime

The target runtime is PostgreSQL through `docker-compose.yml`.

Docker Compose configuration is prepared for:

- `postgres` on `localhost:5432`;
- `backend` on `localhost:8000`;
- `frontend` on `localhost:5173`;
- persistent `postgres_data` and `frontend_node_modules` volumes.

Docker is currently available on this machine. If Docker/PostgreSQL is unavailable in another environment, local manual testing can use the temporary SQLite fallback:

```powershell
cd backend
$env:DATABASE_URL='sqlite:///./buy_modern_dev.db'
python -c "from app.db.session import Base, engine; import app.db.base; Base.metadata.create_all(engine)"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

This fallback is only for local development. PostgreSQL remains the intended database.

See `docs/development-setup.md` for the PostgreSQL/Docker workflow.

## Verification

Latest checks:

- backend tests: `99 passed` on 2026-06-17;
- print form targeted tests: `6 passed` on 2026-06-17 after legacy outgoing invoice layout update;
- print form targeted tests: `10 passed` on 2026-06-18 after PDF invoice export;
- product category targeted tests: `4 passed` on 2026-06-18;
- backend compileall: successful on 2026-06-17;
- frontend TypeScript check: successful on 2026-06-17;
- frontend production build: successful on 2026-06-17.
- Docker Compose smoke: successful on 2026-05-03.
- Production Docker Compose smoke: successful on 2026-05-03.

Deployment smoke details: `docs/deployment-smoke.md`.

## Legacy Dependency

Legacy discovery is still unresolved. Any final accounting behavior must be confirmed from observed old-program behavior, operator knowledge, exports, screenshots, or manual control scenarios before implementation.

The required production data set includes products, warehouses, partners, stock balances, debts, cash, documents, and payments. Because direct `BUY.GDB` access is still blocked by InterBase/ODS compatibility, the first migration path is a controlled manual minimum documented in `docs/legacy-data-readiness.md`.
