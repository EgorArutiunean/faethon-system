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
- Transfer: `quantity_delta = -line.quantity` on source warehouse and `quantity_delta = line.quantity` on destination warehouse
- Cancellation: creates opposite deltas for original posting movements

Commercial default: adjustment line quantity is a target final stock quantity, not a delta.

## Constraints

Outgoing and transfer source movement cannot make stock negative.

Commercial default: negative stock is not permitted for launch.
