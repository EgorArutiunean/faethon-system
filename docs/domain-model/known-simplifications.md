# Known Simplifications

The current implementation is intentionally limited.

Not implemented in this stage:

- full cash book behavior;
- bank accounts;
- multiple cash desks;
- multi-currency cash;
- payment allocation to specific document lines or invoices;
- debt aging;
- returns/refunds with legacy-compatible direction rules;
- VAT;
- discounts;
- foreign-currency supplier debt and exchange-rate gain/loss;
- price lists;
- period closing;
- advanced permissions beyond simple role/object/action checks;
- PDF report export;
- configurable report builder;
- advanced keyboard-first operator workflow;
- saved filters and configurable table columns;
- automatic legacy database import;
- fuzzy matching or overwrite mode for imports;
- import rollback UI after apply;
- automated zero-downtime deployment;
- automated schema rollback;
- legacy report parity.
- draft payment edit/delete UI and API.
- user/role administration UI.

Temporary assumptions:

- document numbering is global per document type;
- document totals are simple `quantity * price`;
- draft deletion is physical deletion, not an archived draft state;
- stock posting is immediate;
- cancellation reverses posting movements;
- adjustment line quantity is treated as target balance;
- partner debt is calculated dynamically from posted documents and posted payments;
- outgoing documents increase partner debt;
- incoming documents reduce partner balance as a simplified supplier payable model;
- customer payments create `cash_in`;
- supplier payments and refunds create `cash_out`;
- cash corrections are treated as signed deltas;
- payment cancellation marks linked cash operations as `cancelled` instead of posting a full legacy reversal workflow;
- authentication uses simple JWT tokens and role permissions;
- no role hierarchy, sharing rules, field-level security, permission sets, or approval workflows;
- reports are simple fixed BuySell-like views over current MVP tables;
- XLSX/CSV exports use simple technical layouts, not legacy print forms;
- document invoice print form has HTML/browser-print and server-side PDF output;
- invoice print layout is a simple BuySell-like placeholder pending legacy confirmation;
- table search/sort/pagination is client-side over currently loaded rows;
- current stock shown in Document Editor is informational and does not replace posting validation;
- Import Lite uses fixed CSV/XLSX templates and does not read `BUY.GDB`;
- opening stock import writes direct stock balance and movement rows;
- opening partner balances use special posted documents to affect current partner balance;
- production deployment is Docker Compose based and does not include TLS automation or external secret management;
- stock movement report dates use movement creation timestamps;
- report totals are calculated over the filtered report rows;
- seeded demo users and passwords are demo-only;
- audit log stores simple action text.
- existing partners default to `both` during migration because old BuySell partner direction is not available yet.

Every temporary accounting rule must be revisited after legacy discovery.
