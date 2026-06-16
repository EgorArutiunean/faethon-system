# Document Lifecycle

## Statuses

- `draft`: editable document, not reflected in stock.
- `posted`: stock movements have been created and balances updated.
- `cancelled`: posted document has been reversed by opposite stock movements.

## Types

- `incoming`: increases stock.
- `outgoing`: decreases stock.
- `adjustment`: currently treats line quantity as target stock quantity.
- `transfer`: moves stock from source warehouse to destination warehouse.

## Numbering

Current temporary numbering:

- incoming: `IN-000001`
- outgoing: `OUT-000001`
- adjustment: `ADJ-000001`
- transfer: `TR-000001`

TODO LEGACY_RULE_REQUIRED: confirm legacy numbering by period, organization, document subtype, warehouse, and concurrency requirements.

## Posting

Posting a draft document:

1. Validates that a warehouse exists.
2. Validates that at least one line exists.
3. Validates partner type:
   - incoming requires `supplier` or `both`;
   - outgoing requires `customer` or `both`;
   - adjustment can be warehouse-only or use any partner type.
4. Calculates stock deltas by document type.
5. Creates `stock_movements`.
6. Updates `stock_balances`.
7. Writes `audit_log`.
8. Sets status to `posted`.

Outgoing and transfer documents are rejected if source stock is insufficient. Transfer documents require source and destination warehouses, the warehouses must be different, and no partner is allowed.

## Editing

Draft documents are editable:

- header fields can be changed while status is `draft`;
- lines can be added, updated, and deleted while status is `draft`;
- total amount is recalculated after line changes.

Posted and cancelled documents are read-only:

- posted documents cannot be updated or deleted;
- cancelled documents cannot be updated or deleted;
- posted documents can only be cancelled through the cancellation flow.

Successful header updates, line deletion, and draft deletion write `audit_log`.

## Cancellation

Cancelling a posted document:

1. Finds posting movements for that document.
2. Creates reverse movements.
3. Updates balances.
4. Writes `audit_log`.
5. Sets status to `cancelled`.

TODO LEGACY_RULE_REQUIRED: confirm cancellation rules when later documents have consumed or depended on the stock.

## Deletion

Only draft documents can be deleted.

Posted documents must not be deleted. Cancel them instead.

Cancelled documents are retained and are not physically deleted.

TODO LEGACY_RULE_REQUIRED: confirm whether legacy BuySell keeps deleted draft documents in an archive/log or physically removes them.
