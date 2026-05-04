# Partners

Partners represent BuySell counterparties. They are intentionally split by operational type, not by CRM account model.

## Types

- `customer`: can be used for outgoing documents and customer payments.
- `supplier`: can be used for incoming documents and supplier payments.
- `both`: can be used in both customer and supplier flows.

Existing rows receive `both` in migration `0004_partner_type`. This is the safest compatibility default because historical data may contain counterparties used in both directions.

## Business Rules

- Incoming document requires a `supplier` or `both` partner.
- Outgoing document requires a `customer` or `both` partner.
- Adjustment document can have no partner or any partner type.
- `customer_payment` requires a `customer` or `both` partner.
- `supplier_payment` requires a `supplier` or `both` partner.
- `refund` keeps the current simplified behavior.

TODO LEGACY_RULE_REQUIRED: confirm refund direction and whether BuySell had separate customer/supplier directories or a shared counterparty table with flags.

## Delete Rules

Partners can be physically deleted only when unused.

Delete is rejected with `409` if the partner is referenced by documents or payments. Used partners should remain for audit/history.

## Import

Partners import requires `partner_type` with one of:

- `customer`
- `supplier`
- `both`

Old files without `partner_type` fail dry-run validation with a clear missing-field error.
