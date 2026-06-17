# Print Forms

Print Forms Core starts with one legacy-oriented HTML document form: invoice / накладная.

Implemented endpoint:

- `GET /api/v1/documents/{id}/print`
- `GET /api/v1/documents/{id}/print.html`

Both endpoints require `documents.read`.

## Invoice Form

The current invoice is an HTML print view rendered from `backend/app/templates/invoice.html`.

As of 2026-06-17, the outgoing invoice layout is aligned to the observed old program screenshot for releasing goods from own warehouse to a customer.

It includes the legacy visual structure:

- centered title like `РАСХОДНАЯ НАКЛАДНАЯ № ...`;
- date in `YYYY.MM.DD` format;
- supplier line populated from the source warehouse name;
- buyer line populated from the customer name;
- visible but currently empty доверенность number/date fields;
- released-by note line;
- compact table columns: `№`, `Код`, `Товар`, `Ед.`, `Кол.`, `Цена`, `Сумма`;
- product code from SKU;
- unit from product unit short name, fallback `шт`;
- quantity without redundant trailing zeros;
- price with three decimals, e.g. `8.000`;
- line/document totals with two decimals, e.g. `136.00`;
- total amount in Russian words;
- `Отпустил` and `Получил` signature lines.

Draft, posted, and cancelled documents can all be previewed. Draft/cancelled documents still receive a watermark, while posted documents print without it.

## Frontend Behavior

The frontend fetches the print HTML with the current bearer token and opens a temporary Blob URL in a new tab. This keeps the endpoint protected by `documents.read` while still allowing browser print.

## Current Limits

- No server-side PDF generation yet.
- No act reconciliation form.
- No cash receipt form.
- No template designer.
- Only the outgoing warehouse-to-customer invoice has a screenshot-backed legacy layout.
- Exact legal fields, numbering rules, and other document form variants are still not fully confirmed.

TODO LEGACY_RULE_REQUIRED: confirm whether `Доверенность №`, `от`, `Отпущено`, numeric-only document number, and draft/cancelled watermarks must exactly match the old program rules.
