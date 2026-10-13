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
## FirstAID discovery update (2026-09-05)

Low-level preview identifies the file as InterBase 7.1 / ODS 11.1, dialect 1,
page size 4096, with 68 relations and zero bad pages. The following relation
names were observed; mappings remain provisional until DDL and samples are
captured:

| Legacy relation | Provisional meaning | Migration relevance |
| --- | --- | --- |
| `CURRENSY` | Historical currency rates (`DATECUR_`, `PREISW_`, `PREISB_`, currency reference) | Optional/reference |
| `SWAEHR` | Currency classifier | Yes if referenced by product prices |
| `KONTR` | Counterparties | Yes, subject to PII minimisation |
| `LICO` | Natural persons with passport/birth data | Do not export wholesale |
| `OSTATOK` | Stock balances | Separate cutoff input; inspect linkage |
| `SEDIZM` | Units of measure classifier; 14 values observed | Yes |
| `SGRP` | Product-group dictionary; 25 codes observed | Yes, with quarantine for blank code text |
| `STOVAR` | Product directory (`GRP_`, `VID_`, `KOD_`, `TEXT_` observed) | Yes |
| `SPODR` | Divisions/warehouses classifier | Inspect next |
| `SDOK` | Document type classifier | No history migration; useful for understanding |
| `NAKLAD`, `LISTDOK`, `SODDOK` | Document header/register/content candidates | No history migration |
| `OPLATA`, `LISTPLAT`, `KASBOOK`, `PROVODKA`, `SALDO`, `OBOROT` | Financial/ledger candidates | No history migration |

Confirmed samples:

- `SEDIZM`: 14 units of measure (`шт.`, `кг.`, `гр.`, `литр`, `пач.`,
  `упак.`, `бут.`, `кор.`, `бан.`, `кв.м.`, `метр`, `компл.`, `лист`,
  `м/п`). Preserve legacy ID and original text.
- `SGRP`: product-group dictionary with 25 observed legacy codes. It mixes
  generic categories (beverages, groceries, juice, confectionery, household
  chemicals, vegetables/fruit) and brand-like group values (`Франзелуца`,
  `BUCURIA`, `GELIBERT`, etc.). Code `710000` has blank visible text and must be
  quarantined for review rather than imported as a normal category.
