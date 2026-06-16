# Legacy Behavior Reconstruction

Date: 2026-06-16

Purpose: rebuild the old BuySell behavior in the modern app without direct `BUY.GDB` access.

The source of truth is observed behavior: old screens, operator explanations, printed forms, reports, screenshots, manual exports, and confirmed decisions. `BUY.GDB` access is not required for progress.

## Decision Status

Use these statuses consistently:

- `confirmed`: Egor confirmed the rule or it was observed in the old program.
- `assumed`: implemented from typical accounting behavior, but not confirmed.
- `question`: needs Egor's answer before implementation.
- `implemented`: already represented in code and covered by tests or smoke checks.
- `deferred`: not needed for the next release unless priority changes.

Risk rule:

- low-risk UI and CRUD behavior can be predicted and implemented;
- stock, money, debts, cash, permissions, reports, cancellation, numbering, and print forms require confirmation before final parity claims.

## Current Implementation Map

| Area | Current behavior | Status | Code/test impact |
| --- | --- | --- | --- |
| Products | CRUD, safe delete when unused, search/sort/pagination in UI | implemented | Keep as baseline |
| Warehouses | CRUD, safe delete when unused | implemented | Keep as baseline |
| Partners | `customer`, `supplier`, `both`; document/payment validation uses type | assumed | Confirm old customer/supplier model |
| Documents | `draft`, `posted`, `cancelled`; draft editable; posted/cancelled read-only | assumed | Confirm lifecycle and deletion rules |
| Numbering | `IN-000001`, `OUT-000001`, `ADJ-000001`, `TR-000001` per document type | assumed | Replace if old numbering differs |
| Stock posting | incoming adds, outgoing subtracts, adjustment sets target stock, transfer moves between warehouses without partner/debt effect | confirmed | Commercial default selected |
| Negative stock | outgoing and transfer posting are blocked when stock is insufficient | confirmed | Commercial default selected |
| Cancellation | posted document creates reverse stock movements; blocked if reversal makes stock negative | assumed | Confirm dependency behavior |
| Debts | outgoing increases customer debt; incoming reduces supplier balance; adjustment ignored | assumed | Confirm signs and supplier presentation |
| Payments | customer payment, supplier payment, refund; posted payments affect balances | assumed | Confirm refund and allocation rules |
| Cash | customer payment creates `cash_in`; supplier/refund creates `cash_out` | assumed | Confirm old cash book behavior |
| Payment cancellation | payment becomes `cancelled`; linked posted cash operations become `cancelled` | assumed | Confirm whether old program used reversals |
| Reports | fixed stock, movement, debt, cash, and document reports with CSV/XLSX export | assumed | Confirm report list, columns, signs, totals |
| Print form | protected HTML document print view | assumed | Confirm exact legacy layout and PDF need |
| Permissions | demo role model: admin, manager, cashier, viewer | assumed | Confirm real roles and user management needs |
| Interface language | The application UI must be Russian | confirmed | Russian is the only active UI language |
| Opening data | Import Lite for products, partners, warehouses, opening stock, opening partner balances | implemented | Add manual data workflow and reconciliation |

## P0 Questions: Documents And Stock

These questions must be answered before changing accounting rules for documents and stock.

| ID | Priority | Question | Current assumption | Status | Code/test impact |
| --- | --- | --- | --- | --- | --- |
| DOC-001 | P0 | What document types should exist at launch? | incoming, outgoing, adjustment, transfer | confirmed | Models, UI labels, posting rules, reports |
| DOC-002 | P0 | How were document numbers generated? | Global sequence per type with `IN/OUT/ADJ/TR` prefixes | assumed | `documents_service._generate_document_number`, tests |
| DOC-003 | P0 | Could users edit a posted document directly? | No; posted documents are read-only | question | API update guards, frontend disabled states |
| DOC-004 | P0 | Could users delete posted or cancelled documents? | No; only draft documents can be deleted | question | Delete endpoint behavior, audit policy |
| DOC-005 | P0 | What happened when cancelling a posted document after later documents consumed its stock? | Block cancellation if reversal makes stock negative | question | Cancellation algorithm and error messages |
| DOC-006 | P0 | Should the app allow selling or transferring more than available stock? | No; insufficient stock blocks posting | confirmed | Posting validation, role exceptions |
| DOC-007 | P0 | What should an adjustment document line mean? | Target final stock quantity | confirmed | Adjustment delta calculation, import opening stock |
| DOC-008 | P0 | Should warehouse transfers be a separate document type? | Yes | confirmed | New document type and transfer workflow |
| DOC-009 | P0 | Did stock have valuation/cost accounting or only quantities? | Quantities only in current stock reports | question | Stock models, reports, import data |
| DOC-010 | P0 | Which date controls stock movement date: document date or posting time? | Movement rows use created timestamp in reports | question | Movement schema/report filters |

## P1 Questions: Debts, Payments, Cash

| ID | Priority | Question | Current assumption | Status | Code/test impact |
| --- | --- | --- | --- | --- | --- |
| DEBT-001 | P1 | How should customer debt and supplier payable signs be shown? | Positive means partner owes us; negative means we owe/credit | question | Reports, statements, UI labels |
| DEBT-002 | P1 | Did incoming supplier documents create payable debt? | Incoming reduces balance as simplified supplier model | question | Debt calculations and tests |
| PAY-001 | P1 | Were payments allocated to specific invoices/documents? | Payment may reference a document, but no allocation rules | question | Payment schema, statement matching |
| PAY-002 | P1 | How were partial payments and overpayments shown? | Balance can become negative | question | Partner statement and reports |
| PAY-003 | P1 | What is the exact refund direction? | Refund increases partner balance and creates `cash_out` | question | Payment effects, cash effects, UI labels |
| PAY-004 | P1 | On payment cancellation, did old program mark cash rows cancelled or add reversal rows? | Mark linked cash rows cancelled | question | Cash cancellation workflow |
| CASH-001 | P1 | Is cash correction a signed delta or an absolute target balance? | Signed delta | question | Cash balance, cash book, reports |
| CASH-002 | P1 | Did old program support multiple cash desks or bank accounts? | Not implemented | question | Cash model, permissions, reports |

## P1 Questions: Reports And Printing

| ID | Priority | Question | Current assumption | Status | Code/test impact |
| --- | --- | --- | --- | --- | --- |
| REP-001 | P1 | Which reports are required for daily work? | Stock balances, stock movements, debts, cash book, documents register | question | Reports page and API scope |
| REP-002 | P1 | What are exact report columns, order, filters, and totals? | Current MVP technical layouts | question | Report schemas and exports |
| REP-003 | P1 | Should reports include cancelled/draft documents? | Most reports use posted/current records only | question | Report filters and totals |
| REP-004 | P1 | Are XLSX/CSV enough, or is PDF/print required? | XLSX/CSV implemented, PDF deferred | question | Export service and UI |
| PRINT-001 | P1 | What is the final invoice title and field list? | Generic BuySell-like invoice | question | `invoice.html`, frontend print flow |
| PRINT-002 | P1 | Are signatures, legal fields, company stamp, or watermarks required? | Signature lines only | question | Print template and PDF |

## P2 Questions: Permissions And Product Completeness

| ID | Priority | Question | Current assumption | Status | Code/test impact |
| --- | --- | --- | --- | --- | --- |
| AUTH-001 | P2 | What real roles exist in the business? | admin, manager, cashier, viewer | question | Seed data, permissions, UI |
| AUTH-002 | P2 | Is user/role management required before launch? | Missing and listed as high priority if needed | question | New admin UI/API |
| AUDIT-001 | P2 | Who needs to view audit history? | Audit rows exist, viewer UI missing | question | Audit API/UI |
| UX-001 | P2 | Which keyboard shortcuts or operator workflows are mandatory? | Basic mouse-first UI | question | Frontend workflow changes |
| UI-001 | P2 | What language must the interface use? | Russian only | confirmed | Disable English switching; keep Russian as active language |
| DATA-001 | P2 | What launch cutoff date should opening balances use? | Not set | question | Manual data readiness |

## Confirmed Decisions

- UI-001: the application interface must be in Russian. English may remain as an internal fallback dictionary, but users should not switch the active UI to English.
- DOC-001/DOC-006/DOC-007/DOC-008: use commercial stock-accounting defaults. Launch document types are incoming, outgoing, adjustment, and transfer. Outgoing/transfer cannot make stock negative. Adjustment quantity means target final stock. Transfer is a warehouse-to-warehouse document with source and destination warehouses and no partner/debt effect.

When Egor answers a question:

1. Move the question status from `question` to `confirmed`.
2. Add a short decision note here.
3. Update the affected domain-model document.
4. Implement code changes if needed.
5. Add or update backend/frontend tests.

## Next Work Block

Start with `DOC-001` through `DOC-010`.

Implementation should not change document or stock accounting behavior until those answers are captured, unless the change is low-risk documentation or UI labeling.
