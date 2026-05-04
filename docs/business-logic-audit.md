# Business Logic Audit

Date: 2026-05-04

Scope: current Buy Modern MVP after partner type split. Legacy discovery was not touched.

| Entity | Create | Read | Update | Delete/Archive/Cancel | Validation | Permissions | Audit | Frontend UI | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Products | Yes | Yes | Yes | Delete only when unused | Name/price schema validation; used product delete returns 409 | `products.*` | Create/update/delete | Create/edit/delete table actions | OK | Archive is not implemented; physical delete only for unused rows. |
| Warehouses | Yes | Yes | Yes | Delete only when unused | Used warehouse delete returns 409 | `warehouses.*` | Create/update/delete | Create/edit/delete table actions | OK | Used in documents/stock balances/movements blocks delete. |
| Partners | Yes | Yes | Yes | Delete only when unused | `partner_type` required: `customer`, `supplier`, `both`; used partner delete returns 409 | `partners.*` | Create/update/delete | Create/edit/delete, type column/filter, statement link | OK | Existing data gets `both` through migration default. |
| Documents / Invoices | Yes | Yes | Draft only | Draft delete; posted cancel; cancelled retained | Type/status rules, partner type rules, stock availability, line totals | `documents.*`, separate post/cancel/delete | Create/update/post/cancel/delete-line/delete-draft | List/editor actions, print, read-only states | OK | Final legacy posting/cancellation rules still TODO. |
| Payments | Yes | Yes | No draft edit UI/API yet | Posted cancel; no physical delete | Payment type and partner type rules; posted/cancelled protected | `payments.read/create/post/cancel` | Create/post/cancel | Create/post/cancel, cash link | P2 | Draft edit/delete is useful but not blocking current accounting flow. |
| Cash Operations | Manual create and payment-created | Yes | No | Posted cancel; cancelled excluded from balance | Type/status rules; cancelled ignored | `cash.read/create/cancel` | Create/cancel and payment cancellation | Cash page create/cancel/book | OK | No physical delete by design. |
| Reports | No writes | Yes | No | No | Fixed filters; export reuses filters | `reports.read` | No data mutations | Tabs, filters, export | OK | Reports are read-only fixed BuySell-like views. |
| Import Lite | Apply creates data/opening entries | Dry-run/template | No overwrite mode | No rollback UI | Required fields, numbers, duplicates, references, `partner_type` | `settings.manage` | Apply audit row | Template/dry-run/apply UI | OK | Dry-run does not mutate data; apply is transactional. |
| Users/Roles/Permissions | Seed only | Current user | No admin UI | No admin UI | JWT auth; role permissions | API returns 401/403 | Auth seed only | Login/logout, protected routes/actions | P2 | User management UI is intentionally deferred. |

## P0/P1 Fixes Applied

- Added partner classification: `customer`, `supplier`, `both`.
- Added Alembic migration with `both` default for existing rows.
- Enforced partner type rules for incoming/outgoing documents and customer/supplier payments.
- Added partner type to partner debts report and export.
- Added partner type to partners import template and validation.
- Added safe delete checks and audit logging for products, warehouses, and partners.
- Added frontend edit/delete actions for products, warehouses, and partners.
- Added frontend partner type selection/filtering and document/payment partner filtering.

## Remaining P2 Items

- Draft payment edit/delete can be added later if operators need it.
- Users/Roles/Permissions still have seed-based management only.
- Archive instead of physical delete for unused catalog rows is not implemented.
- Audit log remains a simple technical log without a viewer UI.

TODO LEGACY_RULE_REQUIRED: confirm whether BuySell allowed one legal entity to be both customer and supplier by default, and whether old partner directories had separate tables or flags.
