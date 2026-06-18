# Manual QA Checklist

Use this checklist against a local demo database after migrations and seed data.

Recommended setup:

```powershell
Copy-Item .env.example .env
make db
make migrate
make seed
make dev
```

If Docker/PostgreSQL is not available, use the documented temporary SQLite fallback for local-only QA.

## PostgreSQL/Docker Smoke

- Verify Docker Desktop is installed and `docker compose version` works.
- Run `Copy-Item .env.example .env`.
- Run `make db`.
- Run `make migrate`.
- Run `make seed`.
- Run `make dev`.
- Open backend health: `http://localhost:8000/health`.
- Open frontend: `http://localhost:5173`.
- Log in as `admin@example.com / admin123`.
- Open Products, Documents, Stock, Payments, Cash, and Reports.
- Open a document print form.
- Export one report as XLSX.
- Export one report as CSV.

Expected result: the MVP runs against PostgreSQL, not SQLite. On 2026-05-02 this smoke was blocked locally because `docker` was not available in `PATH`.

## Production Deployment Smoke

- Copy `.env.production.example` to `.env.production`.
- Set strong `POSTGRES_PASSWORD` and `AUTH_SECRET_KEY`.
- Run `docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`.
- Run migrations with `docker compose --env-file .env.production -f docker-compose.prod.yml run --rm backend alembic upgrade head`.
- Seed demo/admin users only for a controlled environment.
- Verify `http://server/health`.
- Verify frontend loads through nginx.
- Verify login, Documents, Print, Reports Export, and Import dry-run.
- Run a PostgreSQL backup script and confirm a `.dump` file is created.

Expected result: production compose runs with named volumes, restart policies, healthchecks, nginx SPA fallback, `/api` proxy, and env-only credentials. On this machine this smoke is blocked because Docker is unavailable.

## Navigation

- Open Login.
- Sign in as `admin@example.com` / `admin123`.
- Open Dashboard.
- Open Products.
- Open Partners.
- Open Warehouses.
- Open Documents.
- Open one Document Editor from the Documents table.
- Open Stock.
- Open Payments.
- Open Cash.
- Open Reports.
- Open Partners and then a Partner Statement link.

Expected result: every page opens without a blank screen, and API errors are shown as visible error messages.

## Auth And Permissions

- Open the app without a token.
- Verify it redirects to Login.
- Log in as demo admin.
- Verify header shows the user email and role.
- Click Logout.
- Verify the token is removed and Login is shown again.
- For a non-admin test user, verify restricted actions are disabled or return HTTP 403.

Expected result: unauthenticated API calls return HTTP 401, missing permissions return HTTP 403, and admin can use all current MVP actions.

## Role-Based QA

Demo users:

| Email | Password | Role |
| --- | --- | --- |
| `admin@example.com` | `admin123` | `admin` |
| `manager@example.com` | `manager123` | `manager` |
| `cashier@example.com` | `cashier123` | `cashier` |
| `viewer@example.com` | `viewer123` | `viewer` |

Checklist:

- Log in as each demo user and verify the header shows the correct email and role.
- Admin can read/create products, post/cancel documents, post/cancel payments, and create/cancel cash operations.
- Manager can work with products, warehouses, partners, documents, and stock; Settings/users and cash actions are unavailable.
- Cashier can read partners, work with payments and cash, and cannot post documents.
- Viewer can read main sections and cannot create, post, or cancel records.
- Verify Settings is hidden for non-admin users.
- Verify disabled/hidden actions match missing permissions.
- Click Logout and verify token cleanup returns the user to Login.

Expected result: role capabilities match `docs/role-based-qa.md`; forbidden API actions return HTTP 403 and unauthenticated access returns HTTP 401.

## Products

- Verify demo products are visible: `DEMO-BOLT`, `DEMO-CABLE`, `DEMO-LAMP`.
- Create a new product with SKU, name, and base price.
- Refresh the page and confirm it remains visible.

Expected result: product table is populated, and the empty state appears only when there are no products.

## Warehouses

- Verify demo warehouses are visible: `DEMO-MAIN`, `DEMO-RETAIL`.
- Create a new warehouse.

Expected result: warehouse table is populated, and the empty state appears only when there are no warehouses.

## Documents

- Verify seeded incoming and outgoing documents exist.
- Create a new draft document.
- Open it in Document Editor.
- Set type, date, warehouse, and partner.
- Search products by name or SKU in the line entry area.
- Select a product by name and verify price is filled from base price when available.
- Verify current stock balance appears after product and warehouse are selected.
- Add at least one line.
- Verify line total and document total.
- Delete a draft line and verify document total recalculates.
- Edit draft header fields: date, type, warehouse, partner, note.
- Delete a draft document from Documents list or Document Editor.
- Post a document and verify header/line fields become read-only.
- Try deleting a posted document and verify it is forbidden/unavailable.
- Cancel a posted document and verify it becomes read-only.
- Try editing a cancelled document and verify it is forbidden/unavailable.
- Try quantity `0` and verify a validation warning.
- Try negative price and verify a validation warning.
- Try posting and verify a confirmation dialog appears.
- Try cancelling and verify a confirmation dialog appears.
- Click Print from the Documents list.
- Click Print from Document Editor.
- Verify the print view opens in a new tab and shows number, date, type, status, warehouse, partner, lines, quantities, prices, line totals, total amount, and signature lines.

Expected result: draft document can be edited/deleted, draft lines can be deleted with total recalculation, posted documents can only be cancelled, cancelled documents remain read-only, and the invoice print form is available for draft/posted/cancelled documents.

TODO LEGACY_RULE_REQUIRED: confirm exact BuySell invoice title, columns, legal fields, and signature labels.

## Posting

- Post an incoming document.
- Open Stock -> Balances.
- Filter by warehouse.
- Search by product name.

Expected result: incoming document increases stock balance.

## Outgoing And Insufficient Stock

- Create an outgoing document with quantity less than available stock.
- Post it.
- Verify Stock -> Balances decreases.
- Create another outgoing document with quantity greater than available stock.
- Try to post it.

Expected result: posting fails with an API error containing `Not enough stock for outgoing document`.

## Stock Movements

- Open Stock -> Movements.
- Filter by warehouse.
- Search by product or document number.

Expected result: posted documents create movement rows with document number, product, warehouse, movement type, and quantity.

## Payments

- Open Payments.
- Create a draft `customer_payment` for a customer partner.
- Post the payment.
- Verify the Cash column shows a linked cash operation.
- Try to post the same payment again.

Expected result: payment status changes to `posted`; repeated posting fails.

## Cash

- Open Cash.
- Verify the current cash balance is visible.
- Confirm seeded payment operations are visible.
- Create a manual `cash_in` operation.
- Verify cash balance increases.
- Create a manual `cash_out` operation.
- Verify cash balance decreases.
- Create a manual `correction` operation.
- Cancel one posted cash operation.
- Verify cancelled operation remains in the table and no longer affects the balance.

Expected result: cash book rows are ordered by date, statuses are visible, and cancelling a posted operation changes status to `cancelled`.

TODO LEGACY_RULE_REQUIRED: confirm whether corrections are signed deltas or absolute cash balance adjustments.

## Debts

- Open Partners.
- Confirm balances are visible for each partner.
- For a customer with an outgoing document, verify positive balance before payment.
- After customer payment, verify balance decreases.
- If payment is larger than debt, verify balance becomes negative.

Expected result: positive balance means partner owes us; negative balance means credit/prepayment.

TODO LEGACY_RULE_REQUIRED: confirm debt sign presentation against legacy reports.

## Partner Statement

- Open a partner statement from Partners.
- Verify rows include posted documents and payments.
- Check debit, credit, and running balance columns.

Expected result: outgoing document appears as debit; customer payment appears as credit.

TODO LEGACY_RULE_REQUIRED: confirm exact statement ordering and document/payment matching.

## Cancellations

- Cancel a posted payment.
- Verify partner balance returns to the previous debt.
- Open Cash and verify the payment-linked cash operation is marked `cancelled`.
- Cancel a posted document.
- Verify stock balances and partner balance change.
- Try to cancel a draft payment.
- Try to cancel a draft document.

Expected result: cancelling posted records works; cancelling draft records fails with a visible API error.

## Reports

- Open Reports as admin, manager, cashier, and viewer.
- Verify all four roles can read reports because they have `reports.read`.
- Open each tab: Stock Balances, Stock Movements, Debts, Cash Book, Documents Register.
- Apply filters by date, warehouse ID, product ID, partner ID, document ID, type, status, and `only_with_balance` where applicable.
- Verify tables show display names where available: product, warehouse, partner, document number.
- Verify totals are visible: stock quantity, partner debt, cash in/out/balance, and documents total amount.
- Verify empty report states are visible when filters return no rows.
- Verify a user without `reports.read`, if created for testing, receives access denied/HTTP 403.
- Click Export XLSX on each tab and verify a workbook downloads.
- Click Export CSV on each tab and verify the CSV opens in Excel with readable UTF-8 text.
- Apply a filter, export again, and verify the exported rows match the filtered screen.

Expected result: reports are read-only, permission-protected, and XLSX/CSV exports match current MVP data without PDF/print/report-builder features.

## Operator UX

- Verify toast success appears after document create/save/post/cancel/print and report export.
- Verify API errors are shown as toast/error panel.
- Verify insufficient stock appears as a warning with clear text.
- Verify disabled buttons show a permission hint on hover.
- Verify tables support search, sorting by key columns, and pagination when row count exceeds one page.
- Verify status badges are visible for draft/posted/cancelled rows.
- Verify dates and monetary amounts are formatted for operator reading.

Expected result: common operator actions are clear without changing accounting/business rules.

## Import Lite

- Log in as admin.
- Open Settings.
- Verify Import Lite is visible.
- Download templates for products, partners, warehouses, opening stock, and opening partner balances.
- Upload a products CSV/XLSX with a missing required `name` and run Dry run.
- Verify errors are shown and Apply is disabled/refused.
- Upload a products CSV/XLSX with valid rows and run Dry run.
- Apply import and verify products were created.
- Upload warehouses and partners imports and verify rows were created.
- Upload opening stock for an existing product and warehouse.
- Verify Stock balance equals the imported opening quantity.
- Upload opening partner balance for an existing partner.
- Verify partner balance reflects the imported starting debt.
- Log in as viewer and verify Import Lite is not accessible.

Expected result: imports require `settings.manage`, dry-run catches errors before apply, and apply never runs when validation has errors.

TODO LEGACY_RULE_REQUIRED: confirm final opening stock and opening debt representation after legacy discovery.

## Business Logic And Partner Type Smoke

- Products: create a product, edit name/price, delete an unused product, then verify deleting a used product returns a clear 409 error.
- Warehouses: create and edit a warehouse, delete an unused warehouse, then verify deleting a warehouse used by documents/stock returns 409.
- Partners: create `customer`, `supplier`, and `both` partners.
- Partners: verify type column and type filter work.
- Partners: edit partner type on an unused partner and verify save.
- Partners: verify deleting a partner used by documents/payments returns 409.
- Documents: verify incoming partner selector shows suppliers/both.
- Documents: verify outgoing partner selector shows customers/both.
- Documents: changing document type should clear an incompatible selected partner and show a warning.
- Payments: verify customer payment selector shows customers/both.
- Payments: verify supplier payment selector shows suppliers/both.
- Reports: Partner Debts should show partner type and filter by partner type.
- Import Lite: partners template should contain `partner_type`; invalid or missing `partner_type` should fail dry-run.

Expected result: basic CRUD is available for directories, used rows are protected, and customer/supplier rules prevent wrong document/payment combinations.

## Known Manual QA Limits

- VAT, discounts, foreign-currency debts, exchange-rate differences, debts aging, and full cash book workflows are not implemented.
- Server-side PDF generation, advanced print forms, and custom report builder are not implemented.
- Advanced keyboard workflows, saved filters, and configurable tables are not implemented.
- Automatic legacy database import and complex ETL are not implemented.
- Legacy-compatible numbering, cancellation, and statement rules are still pending legacy discovery.
- Do not compare current reports with legacy reports until TODO legacy rules are resolved.

## QA Run 2026-05-02

Environment:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- Database: local SQLite demo database seeded with `seed_demo.py`

Checked and passed:

- Frontend routes return HTTP 200: Dashboard, Products, Partners, Warehouses, Documents, Stock, Payments, Cash, Reports, Settings.
- Demo catalog data is available through API.
- Incoming document posting creates stock balance.
- Posted payment has linked cash operation.
- Cash balance endpoint returns calculated balance.
- RU/EN source dictionaries have matching keys.
- Language selection is persisted in `localStorage` by the frontend i18n provider.

Negative scenarios checked and passed:

- Outgoing document without enough stock returns HTTP 409.
- Re-posting a posted document returns HTTP 409.
- Cancelling a draft document returns HTTP 409.
- Re-posting a posted payment returns HTTP 409.
- Cancelling a draft payment returns HTTP 409.
- Cancelling an already cancelled cash operation returns HTTP 409.

Fixed during QA:

- P1: Russian i18n strings were corrupted by mojibake in source. Replaced RU strings with Unicode escape sequences so the browser renders stable Cyrillic text.
- Role-based QA: no P0/P1 permission defects found. Demo users for admin, manager, cashier, and viewer are seeded with stable credentials.

Not fully browser-automated:

- In-app browser automation was not available in this session because the Node REPL browser tool was not exposed. Frontend verification was performed through Vite route smoke checks and source-level i18n checks.
