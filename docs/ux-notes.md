# UX Notes

Date: 2026-05-02

## Improved

- Document Editor no longer requires manual `product_id` entry.
- Product selection supports filtering by product name and SKU.
- Product base price is copied into the line price when a product is selected.
- Document lines show `product_name`.
- Document header shows current `warehouse_name` and `partner_name`.
- Current stock balance is shown for selected product + warehouse when the user has `stock.read`.
- Quantity must be greater than zero before adding a line.
- Price must be zero or greater before adding a line.
- Insufficient stock conflicts are shown as a clearer operator-facing warning.
- Posting and cancellation require confirmation.
- Toast notifications were added for document create/save/post/cancel/print and report export flows.
- Disabled actions include permission hints via native `title`.
- Tables support basic search, sorting, and pagination.
- Status badges are used for `draft`, `posted`, and `cancelled`.
- Dates and money values are formatted in operator-facing tables.

## Remaining Limits

- Product selection is still an HTML select, not a full keyboard-first command palette.
- Stock balance shown in Document Editor is informational; posting remains the source of truth.
- Toast coverage is focused on the main operator flows, not every secondary screen action.
- Table pagination is client-side over already loaded rows.
- No advanced column customization or saved filters.
- No complex price lists or legacy pricing rules.

TODO LEGACY_RULE_REQUIRED: confirm BuySell keyboard shortcuts, exact operator workflow, product search behavior, and stock warning wording.
