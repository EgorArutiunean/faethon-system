# Work Plan

Date: 2026-06-16

Goal: rebuild the old BuySell program behavior in the modern web app without direct access to `BUY.GDB`.

`BUY.GDB` is no longer treated as a required source. The new source of truth is observed behavior: old program screens, reports, printed forms, operator knowledge, manual exports, screenshots, and confirmed business rules.

## Working Protocol

- Predict and implement behavior when it is obvious, low-risk, and does not affect money, stock, debts, permissions, or legal documents.
- Mark typical but unverified accounting behavior as an assumption until confirmed.
- Ask Egor before implementing any rule that affects stock, money, debts, reports, permissions, document cancellation, numbering, or print forms.
- Convert every confirmed answer into documentation and tests.
- Do not block progress on unavailable `BUY.GDB`; use manual data sources and opening balances.

## Current State

Implemented MVP:

- authentication with demo roles and permissions;
- products, warehouses, and partners;
- draft/posted/cancelled documents;
- document lines, totals, stock posting, warehouse transfer, and cancellation;
- stock balances and movements;
- payments, partner balances, and partner statements;
- cash operations, cash balance, and cash book;
- fixed reports with CSV/XLSX export;
- HTML document print form;
- Import Lite for products, partners, warehouses, opening stock, and opening partner balances;
- Docker Compose development and production configuration;
- GitHub publication to `EgorArutiunean/faethon-system`.

Known limits:

- final legacy-compatible accounting rules are not confirmed;
- full history import from `BUY.GDB` is not available;
- dashboard metrics are live for products, partners, documents, draft payments, stock positions, and cash balance;
- draft payments can be edited and deleted before posting;
- user and role management UI is missing;
- audit log viewer is missing;
- print form is not final legacy-compatible layout;
- PDF generation/export is not implemented;
- advanced reports, saved filters, configurable columns, VAT, discounts, currencies, and period closing are not implemented.

## Phase 1: Behavior Reconstruction

Create and maintain a confirmed behavior map for the old program.

Required outputs:

- list of old program screens and workflows;
- confirmed document types and statuses;
- confirmed stock rules;
- confirmed debt/payment/cash rules;
- confirmed report list, columns, signs, filters, and totals;
- confirmed print forms;
- question log with decisions.

Initial question groups:

- Documents: numbering, document types, draft/edit/delete rules, posting rules, cancellation rules, returns, and insufficient stock behavior.
- Stock: adjustment meaning, negative stock rules, warehouse transfers, stock valuation, and inventory count workflow.
- Partners and debts: customer/supplier classification, debt signs, prepayments, partial payments, overpayments, and statement ordering.
- Payments: customer payments, supplier payments, refunds, allocation to invoices, cancellation behavior, and cash link.
- Cash: operation types, correction meaning, cancellation or reversal behavior, multiple cash desks, and bank operations.
- Reports: required reports, exact column names/order, signs, totals, filters, export formats, and print/PDF needs.
- Permissions: real user roles, forbidden actions, manager/cashier/viewer capabilities, and whether user management is needed before launch.
- Printing: invoice title, legal fields, signatures, status watermarks, and required PDF output.

## Phase 2: Accounting Parity

Turn confirmed behavior into backend rules and tests.

Priority order:

1. Documents and stock posting.
2. Document cancellation and returns.
3. Partner debt calculation and statements.
4. Payments and payment cancellation.
5. Cash book and cash corrections.
6. Report signs, totals, filters, and exports.

Acceptance criteria:

- each confirmed rule has backend tests;
- API errors are explicit and user-readable;
- frontend actions match allowed states;
- reports match agreed control scenarios;
- every remaining assumption is documented.

## Phase 3: Manual Data Start

Start production data from manual sources and opening balances.

Required data:

- products;
- warehouses;
- partners;
- opening stock by product and warehouse;
- opening partner balances;
- opening cash balance;
- optional control documents and payments if available outside `BUY.GDB`.

Acceptance criteria:

- `docs/legacy-data-readiness.md` has a cutoff date;
- every data group has a source;
- Import Lite dry-run passes before apply;
- stock, debt, and cash control totals are reconciled;
- private source files are not committed to Git.

## Phase 4: Product Completeness

Close MVP gaps that affect real daily work.

High priority:

- final enum labels instead of technical codes;
- final document print form;
- user and role management UI if needed for launch;
- audit log viewer if accountability is required.

Medium priority:

- PDF document generation;
- PDF report export;
- saved filters;
- configurable table columns;
- import rollback or reset workflow for test runs;
- better browser-level role and workflow tests.

Deferred until explicitly needed:

- VAT;
- discounts;
- currencies;
- price lists;
- debt aging;
- bank accounts;
- multiple cash desks;
- period closing;
- advanced report builder.

## Phase 5: Production Readiness

Production deployment starts only after behavior and opening data are accepted.

Required before live server:

- VPS/server access;
- domain or stable IP;
- HTTPS decision;
- production PostgreSQL credentials;
- strong `AUTH_SECRET_KEY`;
- initial admin policy;
- backup destination and restore test;
- production smoke checklist.

Acceptance criteria:

- backend tests pass;
- frontend lint and build pass;
- production Docker Compose smoke passes;
- login, documents, stock, payments, cash, reports, export, print, and import dry-run pass;
- first PostgreSQL backup is created and restorable.

## Operating Backlog

Use this order unless Egor changes priority:

1. Build `docs/legacy-behavior-reconstruction.md`.
2. Resolve document and stock questions.
3. Implement confirmed document and stock behavior.
4. Resolve debt, payment, and cash questions.
5. Implement confirmed debt, payment, and cash behavior.
6. Prepare manual opening-data templates and reconciliation flow.
7. Complete high-priority product gaps.
8. Run full acceptance scenarios.
9. Prepare production server deployment.
