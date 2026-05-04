# BuySell To Modern Map

This map preserves BuySell operational language while implementing the new system on a modern stack.

## Terminology

| BuySell / legacy concept | Modern module | Notes |
| --- | --- | --- |
| Товары | Products | Product catalog and prices remain operational, not CRM product marketing. |
| Склады | Warehouses / Stock | Warehouse directory, balances, and movements. |
| Накладные / документы | Documents | Incoming, outgoing, and adjustment documents. |
| Строки документов | Document lines | Quantity, price, line total. |
| Остатки | Stock balances | Calculated from posting movements in the MVP. |
| Движения | Stock movements | Created on document post/cancel. |
| Оплаты | Payments | Partner settlement records. |
| Долги | Partner balances / statements | Calculated from documents and payments. |
| Касса | Cash | Cash operations, cash balance, cash book. |
| Контрагенты | Partners | Customers/suppliers/counterparties. |
| Отчеты | Reports | Placeholder module, not implemented as a report engine yet. |
| Доступ / пользователи | Auth & permissions | Simple role/permission model. |

## Permission Continuity

The modern permissions intentionally stay object/action based:

- read;
- create;
- update;
- delete where needed;
- post/cancel for accounting actions.

This is similar to Salesforce CRUD/action permissions, but does not include role hierarchy, sharing rules, field-level security, permission sets, or approval workflows.

## Current Role Mapping

| Modern role | Intended legacy-style responsibility |
| --- | --- |
| `admin` | Full system administrator. |
| `manager` | Catalog, warehouse, partner, document, stock, and report work. |
| `cashier` | Payments and cash operations. |
| `viewer` | Read-only operational view. |

TODO LEGACY_RULE_REQUIRED: map old BuySell access flags/users after legacy discovery becomes available.

## Partner Direction

Modern partners now have a simple operational type:

| Modern partner type | Intended meaning |
| --- | --- |
| `customer` | Buyer/client used for outgoing invoices and customer payments. |
| `supplier` | Supplier used for incoming invoices and supplier payments. |
| `both` | Counterparty that may be used in both directions. Existing migrated/demo rows may default here until legacy facts are known. |

TODO LEGACY_RULE_REQUIRED: confirm whether legacy BuySell stored customers and suppliers separately or used one shared counterparty list.

## Product Direction

The app should remain a BuySell replacement for accounting and warehouse operations.

Avoid turning the interface into a generic CRM platform:

- keep operational names;
- keep dense tables and forms;
- avoid sales pipeline terminology;
- avoid CRM-only concepts unless they directly support BuySell workflows.
