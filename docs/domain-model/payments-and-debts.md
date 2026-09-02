# Payments And Debts

This stage adds a minimal vertical accounting scenario:

partner -> posted document -> debt -> payment -> remaining debt.

## Balance Sign

The current balance is calculated dynamically.

- positive balance: partner owes us;
- negative balance: we owe the partner or the partner has a credit/prepayment.

This is the accepted operational sign convention for the first release. Its
presentation is still included in business UAT against control totals.

## Document Effects

Only posted documents affect partner balances.

- `outgoing` increases the partner debt by `documents.total_amount`;
- `incoming` decreases the partner balance by `documents.total_amount`;
- `adjustment` does not affect partner debt in the current MVP.

Cancelled and draft documents are ignored.

Transfers and warehouse adjustments do not affect partner debt. The first release
uses controlled correction/reposting or cancellation instead of a separate goods
return document.

## Payment Effects

Only posted payments affect partner balances.

- `customer_payment` decreases the partner debt;
- `supplier_payment` increases the balance because it reduces our payable to a supplier;
- `refund` currently increases the balance.

Partner type validation:

- `customer_payment` requires a `customer` or `both` partner;
- `supplier_payment` requires a `supplier` or `both` partner;
- `refund` keeps the simplified current rule.

Payment cancellation changes the payment status to `cancelled`, writes audit log,
and cancels the linked cash operation.

The standalone `refund` payment direction is not yet approved for production and
must not be treated as a completed first-release workflow.

## Manual Allocation

- one payment can be allocated to multiple posted documents of the same partner;
- customer payments can be allocated only to outgoing documents;
- supplier payments can be allocated only to incoming documents;
- the allocated total cannot exceed the payment amount;
- an allocation cannot exceed the document's outstanding amount;
- draft payments do not reserve document debt;
- posting revalidates allocations while locking the affected documents;
- the unallocated remainder is kept as a partner advance;
- only a manager or administrator can submit or change allocations;
- a cashier can register a payment on account without allocations.

A posted payment can be reallocated without changing its amount, partner, date,
status, or cash balance. The existing cash row is retained and only its related
document reference is synchronized. The allocation change is written to audit.

## Document Interaction

A posted document with active allocations cannot be cancelled. Controlled reposting
cannot change its partner or document type and cannot reduce its total below the
posted allocated amount. The manager must reallocate the payments first.

Cancelling a payment releases its allocations from outstanding calculations.

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
