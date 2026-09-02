# Cash Accounting

Cash Core covers a minimal operational register:

payment -> cash operation -> cash balance -> cash book.

## Operation Types

- `cash_in`: increases cash balance;
- `cash_out`: decreases cash balance;
- `correction`: currently changes balance by signed amount.

TODO LEGACY_RULE_REQUIRED: confirm whether corrections are signed deltas, absolute balance resets, or separate cash documents.

## Statuses

- `posted`: included in cash balance;
- `cancelled`: kept for traceability and excluded from cash balance.

Cash operations are not physically deleted.

## Payment Integration

- `customer_payment` creates `cash_in`;
- `supplier_payment` creates `cash_out`;
- historical `refund` rows keep their existing cash links, but new refund payments
  are disabled for the first release.

Cancelling a posted payment marks linked cash operations as `cancelled` and writes audit log entries.

Bank accounts and standalone refunds are outside the first-release scope. The API
rejects new bank/refund payments instead of mapping them into the single cash desk.

## Cash Balance

Cash balance is calculated dynamically from non-cancelled cash operations.

This MVP does not implement:

- bank accounts;
- multiple cash desks;
- multi-currency cash;
- cashier shifts;
- printed cash orders;
- period closing.
