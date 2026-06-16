# Legacy Data Readiness

Date: 2026-06-16

Production launch is gated on verified legacy data. Direct automated access to `BUY.GDB` is not available yet, so the immediate migration path is a controlled manual minimum with explicit reconciliation.

## Rules

- Do not modify the original `BUY.GDB`.
- Work only from copies, old application exports, printed reports, screenshots, or manually prepared spreadsheets.
- Record the source used for every imported data group.
- Reconcile totals before production use.
- Keep private customer, supplier, and financial exports out of Git unless anonymized.

## Required Data Set

| Area | Required for launch | Current path | Acceptance check |
| --- | --- | --- | --- |
| Products | Yes | Manual spreadsheet or old app export | Product count and sample names/prices match source |
| Warehouses | Yes | Manual spreadsheet or old app export | Warehouse list matches active legacy warehouses |
| Partners | Yes | Manual spreadsheet or old app export | Customer/supplier classification reviewed |
| Stock balances | Yes | Opening stock import | Quantity totals per warehouse match legacy report |
| Partner debts | Yes | Opening partner balance import | Customer and supplier debt totals match legacy report |
| Cash balance | Yes | Manual cash opening operation | Cash total matches legacy cash report |
| Documents | Yes | Manual or staged spreadsheet import | Control documents can be traced to legacy source |
| Payments | Yes | Manual or staged spreadsheet import | Payment totals by partner and period match legacy source |

## Manual Minimum Workflow

1. Freeze a legacy cutoff date and record it in this document.
2. Export or manually prepare CSV/XLSX files for products, warehouses, partners, opening stock, opening partner balances, cash opening balance, documents, and payments.
3. Run Import Lite dry-runs for supported templates and fix validation errors before applying data.
4. Enter unsupported items manually through the UI or add a scoped importer before launch.
5. Compare report totals in the new app against legacy control totals.
6. Record final sign-off values below.

## Control Totals

Fill these before production launch.

| Metric | Legacy total | New app total | Source | Status |
| --- | ---: | ---: | --- | --- |
| Product count |  |  |  | Pending |
| Warehouse count |  |  |  | Pending |
| Partner count |  |  |  | Pending |
| Stock quantity total |  |  |  | Pending |
| Stock value total |  |  |  | Pending |
| Customer debt total |  |  |  | Pending |
| Supplier debt total |  |  |  | Pending |
| Cash balance |  |  |  | Pending |
| Document count |  |  |  | Pending |
| Payment total |  |  |  | Pending |

## Open Blockers

- Original InterBase server/client runtime is still missing.
- `BUY.GDB` metadata and row samples have not been exported.
- Exact legacy posting and cancellation rules remain unconfirmed.
- Production server, domain/IP, HTTPS, secrets, and backup destination are not yet available.
