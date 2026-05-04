# Stock Accounting

## Current Model

Stock is represented by:

- `stock_movements`: append-only movement log for document posting and cancellation.
- `stock_balances`: current aggregate balance per product and warehouse.

The API exposes:

- `GET /api/v1/stock/balances`
- `GET /api/v1/stock/movements`

Both endpoints include display names for products and warehouses.

## Current Movement Rules

- Incoming: `quantity_delta = line.quantity`
- Outgoing: `quantity_delta = -line.quantity`
- Adjustment: `quantity_delta = line.quantity - current_balance`
- Cancellation: creates opposite deltas for original posting movements

TODO LEGACY_RULE_REQUIRED: confirm whether legacy adjustment documents store target balance, correction delta, inventory fact, or another behavior.

## Constraints

Outgoing movement cannot make stock negative.

TODO LEGACY_RULE_REQUIRED: confirm whether legacy system permits negative stock for specific users, warehouses, products, or periods.
