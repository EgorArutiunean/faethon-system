# Print Forms

Print Forms Core starts with one BuySell-like print form: document invoice / накладная.

Implemented endpoint:

- `GET /api/v1/documents/{id}/print`
- `GET /api/v1/documents/{id}/print.html`

Both endpoints require `documents.read`.

## Invoice Form

The current invoice is an HTML print view rendered from `backend/app/templates/invoice.html`.

It includes:

- document number;
- document date;
- document type;
- document status;
- warehouse;
- partner;
- product lines;
- quantity;
- price;
- line total;
- document total;
- signature lines.

Draft, posted, and cancelled documents can all be previewed. The status is printed prominently.

## Frontend Behavior

The frontend fetches the print HTML with the current bearer token and opens a temporary Blob URL in a new tab. This keeps the endpoint protected by `documents.read` while still allowing browser print.

## Current Limits

- No server-side PDF generation yet.
- No act reconciliation form.
- No cash receipt form.
- No template designer.
- No legacy-compatible print layout guarantee until legacy discovery is complete.

TODO LEGACY_RULE_REQUIRED: confirm final BuySell invoice title, columns, legal fields, signature labels, and whether cancelled/draft watermarks are needed.
