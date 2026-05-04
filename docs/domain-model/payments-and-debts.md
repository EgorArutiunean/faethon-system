# Payments And Debts

This stage adds a minimal vertical accounting scenario:

partner -> posted document -> debt -> payment -> remaining debt.

## Balance Sign

The current balance is calculated dynamically.

- positive balance: partner owes us;
- negative balance: we owe the partner or the partner has a credit/prepayment.

TODO LEGACY_RULE_REQUIRED: confirm the exact sign convention, document classes, and report presentation against the legacy application.

## Document Effects

Only posted documents affect partner balances.

- `outgoing` increases the partner debt by `documents.total_amount`;
- `incoming` decreases the partner balance by `documents.total_amount`;
- `adjustment` does not affect partner debt in the current MVP.

Cancelled and draft documents are ignored.

TODO LEGACY_RULE_REQUIRED: confirm how returns, corrections, supplier invoices, and warehouse-only documents affect partner balances.

## Payment Effects

Only posted payments affect partner balances.

- `customer_payment` decreases the partner debt;
- `supplier_payment` increases the balance because it reduces our payable to a supplier;
- `refund` currently increases the balance.

Partner type validation:

- `customer_payment` requires a `customer` or `both` partner;
- `supplier_payment` requires a `supplier` or `both` partner;
- `refund` keeps the simplified current rule.

Payment cancellation changes the payment status to `cancelled`, writes audit log, and records a reversing cash operation.

TODO LEGACY_RULE_REQUIRED: refund direction, settlement matching, and cash book cancellation rules must be restored from legacy behavior.

## Statement

The partner statement combines posted documents and posted payments in date order.

Columns:

- date;
- document/payment source;
- debit;
- credit;
- running balance;
- status.

The statement is a working operational view, not a legacy-compatible report.
