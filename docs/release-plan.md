# Release Plan

Date: 2026-06-18

> Historical plan. Superseded for release decisions by
> `docs/deployment-work-plan.md` (updated 2026-10-11).

Goal: prepare Buy Modern for the fastest safe company transition from the old BuySell program.

## Done

1. GitHub repository is published: `EgorArutiunean/faethon-system`.
2. Local Docker stack works with PostgreSQL, backend, and frontend.
3. Authentication, roles, and permissions are implemented.
4. Product, product category, warehouse, and partner directories are implemented.
5. Documents support draft, posting, cancellation, lines, totals, and stock movements.
6. Stock balances and stock movement views are implemented.
7. Payments, cash operations, cash book, cash balance, partner balances, and statements are implemented.
8. Reports with CSV/XLSX export are implemented.
9. Audit log and admin user management are implemented.
10. Outgoing invoice HTML print form follows the observed old-program layout.
11. Invoice PDF export with readable Russian text is implemented.
12. Import Lite supports reference data and opening balances.
13. The current price-list export was inspected: it contains 382 unique products,
    units, quantities, accounting prices and retail prices. The detailed audit
    and 15 000-row migration design are in `docs/catalog-import-plan.md`.
14. Buy Modern product import standard now includes explicit `category` and `legacy_name` fields.
15. A controlled data-preparation tool converts the known old price-list XLSX shape into Buy Modern `products.xlsx` and `opening-stock.xlsx` templates.
16. Incoming documents support foreign purchase currency, fixed exchange rate, base RUB PMR conversion, and sale-price review hints.
17. A manager can manually allocate payments across posted invoices; partial payments, advances, and reallocation without duplicate cash movements are protected by backend and PostgreSQL E2E tests.
18. Unsupported standalone refunds and bank payments are hidden from the working UI and rejected by the API; historical rows remain readable and cancellable.

## Before Release

1. Confirm the source price semantics, warehouse mapping, snapshot date and
   category rules, then implement `docs/catalog-import-plan.md`.
2. Prepare and reconcile production opening data: products, categories, warehouses, partners, stock, debts, and cash.
3. Confirm remaining print forms and whether invoice PDF needs visual tuning against the old form.
4. Confirm production user list, roles, and whether non-admin users need audit access.
5. Run operator acceptance scenarios: incoming goods, outgoing goods, payment, cash, reports, print, export, import dry-run.
6. Prepare server values: domain or stable IP, HTTPS decision, production PostgreSQL credentials, strong `AUTH_SECRET_KEY`, and initial admin policy.
7. Run production Docker Compose smoke on the target server.
8. Create the first PostgreSQL backup and verify restore.
9. Approve cutover date after control totals match.

## Verified

1. Product import standard fields and price-list data preparation are covered by targeted tests: `12 passed`.
2. Backend test suite passed after the data-preparation tool was added: `109 passed`.
3. Product category targeted tests passed.
4. Currency and incoming document conversion tests passed.
5. Print form targeted tests passed.
6. Frontend production build passed after currency work.
7. Browser smoke for `/products` confirmed Russian category UI with no console errors.
8. Live API accepted UTF-8 Russian category and product names.
9. Historical local smoke succeeded at `http://127.0.0.1:5173` and
   `http://127.0.0.1:8000`; this does not describe the current runtime state.

## Current Priority

1. Confirm the five source-data decisions listed in `docs/catalog-import-plan.md`.
2. Correct the current converter so `Цена Розн.` becomes the sale price and
   `Цена ост.` becomes the auditable opening cost.
3. Add unit mapping, import batches, staging, dry-run and bulk upsert.
4. Move the catalog UI to server-side search and pagination.
5. Rehearse the 382-row import in a clean database and reconcile control totals.
6. Load-test and rehearse the same process with at least 15 000 products.
