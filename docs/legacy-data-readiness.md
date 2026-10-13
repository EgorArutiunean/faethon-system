# Legacy Data Readiness

Date: 2026-09-02

Production launch is gated on verified legacy data. Low-level read-only preview
of `BUY.GDB` is available and has confirmed the key directory tables, but a
repeatable structured export is not available yet. The immediate migration path
therefore remains a controlled minimum with explicit reconciliation.

Scope clarification received on 2026-09-05: `BUY.GDB` is used as the source of
directories/reference data only. Historical documents, payments, cash entries,
and accounting postings are not expected to be migrated from this database.
Operational opening values must therefore come from separate signed cutoff
reports or spreadsheets.

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
| Historical documents | No | Start new operational history after cutoff | Cutoff protocol states that history remains in the legacy archive |
| Historical payments | No | Start new operational history after cutoff | Opening partner balances and cash reconcile without importing payment history |

## Manual Minimum Workflow

1. Freeze a legacy cutoff date and record it in this document.
2. Export directories from `BUY.GDB`: products, product groups, units, warehouses,
   partners and any referenced currencies/price classifiers. Separately prepare
   signed cutoff files for opening stock, partner balances and cash balance.
   The current product/stock export and its required import changes are described
   in `docs/catalog-import-plan.md`. Do not run the existing converter against
   production data until its price mapping is corrected.
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
| Historical document count | Not migrated | Not migrated | Cutoff protocol | Pending confirmation |
| Historical payment total | Not migrated | Not migrated | Cutoff protocol | Pending confirmation |

## Open Blockers

- InterBase 2020 is installed locally, but its server cannot start until the
  Developer Edition registration requirement is resolved.
- FirstAID preview confirmed relation names and representative rows, but no
  versioned DDL/CSV export, complete metadata set or repeatable row extract has
  been produced.
- The current local price-list export has been inspected: 382 product rows and
  control totals are recorded in `docs/catalog-import-plan.md`.
- The currency represented by `у.е.`, the exact meaning of `Цена ост.`, warehouse
  code `4444`, categories, and the snapshot date still require confirmation.
- Exact legacy posting and cancellation rules remain unconfirmed.
- Production server, domain/IP, HTTPS, secrets, and backup destination are not yet available.
