# Multicurrency Purchasing

Buy Modern uses `RUB_PMR` as the base operational currency.

## Implemented Scope

- Default currencies: `RUB_PMR`, `MDL`, `USD`, `EUR`.
- Manual historical exchange rates through `/api/v1/currencies/rates`.
- Incoming documents can store:
  - document currency;
  - exchange rate to `RUB_PMR`;
  - foreign line price and foreign line total;
  - base line price and base line total in `RUB_PMR`;
  - foreign document total and base document total.
- Stock, document totals, reports, sales, cash, and partner balances continue to use `RUB_PMR`.
- In the document editor, incoming purchase price is converted to `RUB_PMR`.
- If the new base purchase cost differs from the current product sale/base price, the operator sees a review hint.

## Current Rule

The exchange rate is fixed on the incoming document. Later rate changes do not recalculate posted or draft document lines automatically.

For incoming documents:

```text
base_price = foreign_price * exchange_rate
base_line_total = quantity * base_price
```

For outgoing, adjustment, and transfer documents:

```text
currency = RUB_PMR
exchange_rate = 1
```

## Not Implemented Yet

- Supplier debt kept in foreign currency.
- Currency payment allocation.
- Exchange-rate gain/loss.
- Automatic rate import from banks or public services.
- Automatic sale price update.
- Margin policy by product category.

These rules must be confirmed before implementation because they affect money, debts, reports, and accounting interpretation.
