# Export Core

Export Core adds simple XLSX and CSV downloads for the fixed Reports Core reports.

Implemented endpoints:

- `GET /api/v1/reports/stock-balances/export?format=xlsx|csv`
- `GET /api/v1/reports/stock-movements/export?format=xlsx|csv`
- `GET /api/v1/reports/partner-debts/export?format=xlsx|csv`
- `GET /api/v1/reports/cash-book/export?format=xlsx|csv`
- `GET /api/v1/reports/documents-register/export?format=xlsx|csv`

All export endpoints require `reports.read`.

## Behavior

- Export uses `reports_service.py` data, so filters and totals match the on-screen reports.
- XLSX files are generated with `openpyxl`.
- CSV files are generated with Python `csv` and encoded as UTF-8 with BOM for Excel compatibility.
- Unsupported formats return HTTP 400.

## XLSX Layout

Each workbook contains:

- report title;
- generation timestamp;
- applied filters, when present;
- table headers and data rows;
- total rows where the report has totals.

## CSV Layout

CSV is a simple technical export:

- column headers;
- data rows;
- total rows after an empty separator row.

## Current Limits

- No PDF.
- No print forms.
- No configurable report builder.
- No styled legacy-compatible BuySell print layout.
- No export audit log.

TODO LEGACY_RULE_REQUIRED: confirm final BuySell-compatible report names, column order, and totals after legacy discovery.
