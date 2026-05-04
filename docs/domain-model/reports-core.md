# Reports Core

Reports Core provides simple BuySell-like operational reports for operators and managers.

Implemented API:

- `GET /api/v1/reports/stock-balances`
- `GET /api/v1/reports/stock-movements`
- `GET /api/v1/reports/partner-debts`
- `GET /api/v1/reports/cash-book`
- `GET /api/v1/reports/documents-register`

All endpoints require `reports.read`.

## Report Types

### Stock Balances

Purpose: show current stock by product and warehouse.

Filters:

- `warehouse_id`
- `product_id`
- `search`

Totals:

- `total_quantity`

Display fields include `product_name`, `warehouse_name`, and `quantity`.

### Stock Movements

Purpose: show posted and reversal stock movement rows.

Filters:

- `date_from`
- `date_to`
- `warehouse_id`
- `product_id`
- `document_id`

Totals:

- `total_quantity`

Display fields include product, warehouse, source document number/type/status, movement type, and quantity delta.

### Partner Debts

Purpose: show simplified partner balances from posted documents and posted payments.

Filters:

- `partner_id`
- `only_with_balance`

Totals:

- `total_partner_debt`

TODO LEGACY_RULE_REQUIRED: confirm debt signs and supplier payable presentation against BuySell reports.

### Cash Book

Purpose: show cash operations and cash totals.

Filters:

- `date_from`
- `date_to`
- `operation_type`
- `status`

Totals:

- `cash_in_total`
- `cash_out_total`
- `cash_balance`

TODO LEGACY_RULE_REQUIRED: confirm whether correction rows are signed deltas or absolute cash balance adjustments.

### Documents Register

Purpose: show a simple register of documents/накладные.

Filters:

- `date_from`
- `date_to`
- `document_type`
- `status`
- `partner_id`
- `warehouse_id`

Totals:

- `total_amount`

Display fields include number, date, type, status, partner, warehouse, and total amount.

## Current Limits

- No XLSX/CSV export.
- No PDF or print forms.
- No configurable report builder.
- No Salesforce-style custom reports.
- No legacy report parity claims until legacy discovery is complete.
