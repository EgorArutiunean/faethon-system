# Cash Core Plan

This document describes the implemented Cash Core and the remaining legacy-dependent gaps.

## Current State

`payments` are operational records for partner settlements.

`cash_operations` are created by `payments_service` when a payment is posted:

- posting `customer_payment` creates a posted cash-in operation;
- posting `supplier_payment` creates a posted cash-out operation;
- posting `refund` currently creates a posted cash-out operation;
- cancelling a posted payment marks linked cash operations as `cancelled`.

Manual cash operations can also be created through the Cash API.

TODO LEGACY_RULE_REQUIRED: confirm whether legacy cancellation edits cash rows, marks them cancelled, posts reversal rows, or uses another register.

## Relationship

Implemented relationship:

- one payment can create one cash operation in the current MVP;
- each cash operation can optionally reference a payment;
- each cash operation can optionally reference a partner and document;
- cash operation amount must never be changed after posting without an audit trail.

The current model has `cash_operations.payment_id`, `partner_id`, `document_id`, and nullable `created_by_id`.

## Operation Types

The cash core has explicit operation type values:

- `cash_in`: money received;
- `cash_out`: money paid;
- `correction`: manual correction.

The model also keeps `direction` for simple sign handling and migration compatibility.

TODO LEGACY_RULE_REQUIRED: confirm legacy cash operation classification and whether bank operations share the same register.

## Statuses

Implemented statuses:

- `posted`;
- `cancelled`.

Draft cash operations are intentionally not planned until the cash workflow is clarified.

TODO LEGACY_RULE_REQUIRED: confirm if legacy has draft/unposted cash documents or only posted cash book rows.

## Implemented API

Implemented endpoints:

- `GET /api/v1/cash/operations`
- `POST /api/v1/cash/operations`
- `POST /api/v1/cash/operations/{id}/cancel`
- `GET /api/v1/cash/balance`
- `GET /api/v1/cash/book`

Filters still needed later:

- date range;
- operation type;
- status;
- partner;
- payment;
- document.

## Frontend

Implemented:

- Cash Operations list;
- Cash Balance summary;
- manual cash operation form;
- cancel action for posted operations.

The UI should remain a dense accounting workspace: tables, filters, statuses, and clear actions.

## Out Of Scope For Now

- cash desks/registers;
- bank accounts;
- multi-currency cash;
- cashier shifts;
- printed cash orders;
- period closing;
- permissions for cash operations.

These must wait for legacy discovery and process confirmation.
