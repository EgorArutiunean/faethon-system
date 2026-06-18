# Import Lite

Import Lite provides a safe manual path to move reference data and opening balances into Buy Modern without reading `BUY.GDB`.

It is intentionally simple:

- fixed CSV/XLSX templates;
- dry-run validation before apply;
- apply only when validation has no errors;
- protected by `settings.manage`;
- no automatic legacy table mapping.

## Templates

Download endpoints:

- `GET /api/v1/import/templates/products.xlsx`
- `GET /api/v1/import/templates/partners.xlsx`
- `GET /api/v1/import/templates/warehouses.xlsx`
- `GET /api/v1/import/templates/opening-stock.xlsx`
- `GET /api/v1/import/templates/opening-partner-balances.xlsx`

Template columns:

| Import | Columns |
| --- | --- |
| Products | `sku`, `name`, `category`, `base_price`, `description`, `legacy_name` |
| Partners | `name`, `partner_type`, `code`, `phone` |
| Warehouses | `name`, `code`, `address` |
| Opening stock | `product_sku`, `product_name`, `warehouse_name`, `quantity` |
| Opening partner balances | `partner_name`, `balance` |

## Product Import

Product import accepts the normal template and a controlled old price-list shape.

Supported old price-list details:

- a title row before the actual header row is allowed;
- Russian headers are normalized: `Код` to `sku`, `Товар` to `name`, `Цена ост.` to `base_price`, `Категория` or `Группа` to `category`;
- when an old price-list row is detected, the raw old product name is saved as `legacy_name` in the product description;
- if `category` is provided, the product group is found by name or created automatically;
- category is not guessed from the product name yet, because that would affect operational data and needs a confirmed rule.

Current price assumption: for old price-list files, `Цена ост.` is imported into `base_price`. This is an operational seed value, not a final legacy price-list model.

## Dry Run

Dry-run endpoints:

- `POST /api/v1/import/products/dry-run`
- `POST /api/v1/import/partners/dry-run`
- `POST /api/v1/import/warehouses/dry-run`
- `POST /api/v1/import/opening-stock/dry-run`
- `POST /api/v1/import/opening-partner-balances/dry-run`

Dry-run checks:

- required fields;
- numeric values;
- duplicates in the uploaded file;
- partner import `partner_type` values: `customer`, `supplier`, `both`;
- referenced product/warehouse for opening stock;
- referenced partner for opening balances.

Response summary:

- `rows_total`
- `rows_valid`
- `rows_invalid`
- `errors`
- `warnings`
- `applied`
- `created`
- `skipped`

## Apply

Apply endpoints:

- `POST /api/v1/import/products/apply`
- `POST /api/v1/import/partners/apply`
- `POST /api/v1/import/warehouses/apply`
- `POST /api/v1/import/opening-stock/apply`
- `POST /api/v1/import/opening-partner-balances/apply`

Apply behavior:

- validation is run first;
- rows are not imported if validation has errors;
- the operation is transactional;
- an `audit_log` row is created;
- existing products are matched by `sku` or `name` and skipped;
- product categories from product import are created when missing;
- existing partners are matched by `name` and skipped;
- existing warehouses are matched by `name` and skipped.

## Opening Stock

Opening stock sets the current `stock_balances.quantity` to the imported quantity and writes a `stock_movements` row with reason `opening:import`.

TODO LEGACY_RULE_REQUIRED: confirm whether opening stock should be represented as a special adjustment document, a direct movement, or another legacy-compatible operation.

## Opening Partner Balances

Opening partner balances are represented by special posted documents:

- positive balance creates an `outgoing` opening document;
- negative balance creates an `incoming` opening document.

This makes the existing partner balance and statement logic reflect the starting debt.

TODO LEGACY_RULE_REQUIRED: replace this representation with confirmed legacy-compatible opening debt behavior.

## Current Limits

- No `BUY.GDB` reader.
- No automatic mapping of all legacy tables.
- No fuzzy matching.
- No automatic category inference from embedded old product names.
- No update/overwrite mode.
- No background import jobs.
- No import rollback UI after apply.
