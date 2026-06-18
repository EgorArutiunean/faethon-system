# Release Plan

Date: 2026-06-18

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
13. Old price-list sample from `E:\primer.xlsx` was inspected: product code, name, unit, quantity, and price data are available; category-like data is embedded in the product name.
14. Buy Modern product import standard now includes explicit `category` and `legacy_name` fields.
15. A controlled data-preparation tool converts the known old price-list XLSX shape into Buy Modern `products.xlsx` and `opening-stock.xlsx` templates.

## Before Release

1. Confirm final document, stock, debt, payment, and cash rules from old-program behavior.
2. Prepare old price-list category mapping and run the data-preparation tool against the real export.
3. Prepare and reconcile production opening data: products, categories, warehouses, partners, stock, debts, and cash.
4. Confirm remaining print forms and whether invoice PDF needs visual tuning against the old form.
5. Confirm production user list, roles, and whether non-admin users need audit access.
6. Run operator acceptance scenarios: incoming goods, outgoing goods, payment, cash, reports, print, export, import dry-run.
7. Prepare server values: domain or stable IP, HTTPS decision, production PostgreSQL credentials, strong `AUTH_SECRET_KEY`, and initial admin policy.
8. Run production Docker Compose smoke on the target server.
9. Create the first PostgreSQL backup and verify restore.
10. Approve cutover date after control totals match.

## Verified

1. Product import standard fields and price-list data preparation are covered by targeted tests: `12 passed`.
2. Backend test suite passed after the data-preparation tool was added: `109 passed`.
3. Product category targeted tests passed.
4. Print form targeted tests passed.
5. Frontend production build passed after category work.
6. Browser smoke for `/products` confirmed Russian category UI with no console errors.
7. Live API accepted UTF-8 Russian category and product names.
8. Local stack is running at `http://127.0.0.1:5173` and `http://127.0.0.1:8000`.

## Current Priority

1. Restore access to the real old price-list file; `E:\primer.xlsx` is not currently available in this workspace.
2. Define or manually prepare the category map for old product names.
3. Run the data-preparation tool against the real old price-list export and inspect generated standard templates.
4. Run Import Lite dry-run for generated `products.xlsx` and `opening-stock.xlsx`.
5. Run full acceptance smoke after import improvements.
