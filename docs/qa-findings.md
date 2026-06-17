# QA Findings

QA run date: 2026-05-02

## P0

No open P0 issues found.

## P1

- Fixed: Russian UI text was corrupted in `frontend/src/i18n.tsx`.
  - Impact: RU mode rendered unreadable text.
  - Resolution: replaced RU strings with Unicode escape sequences to avoid Windows/PowerShell encoding drift.
  - Verification: `npx tsc -b` passes; mojibake scan over `frontend/src` returns no matches.

## P2

- Some domain values are still shown as system codes.
  - Examples: `incoming`, `outgoing`, `cash_in`, `cash_out`, `posted`, `cancelled`.
  - Recommendation: add enum display labels later without changing API payload values.

- Fixed: Dashboard metrics are loaded from live API data.
  - Coverage: products, partners, documents, draft payments, stock positions, and cash balance.
  - Verification: frontend TypeScript check and production build pass; browser preview showed live demo values.

- Fixed: Draft payments can be edited and deleted before posting.
  - Coverage: backend service/API protection for draft-only update/delete; frontend edit/save/delete controls on the payments page.
  - Verification: payment service tests pass; frontend TypeScript check passes.

- Fixed: Outgoing invoice print form follows the observed old program layout for releasing goods from own warehouse to a customer.
  - Coverage: title, date, supplier warehouse, buyer, trust letter placeholders, legacy columns, SKU code, unit, quantity, three-decimal price, two-decimal totals, Russian amount words, and `Отпустил`/`Получил` signatures.
  - Verification: targeted print form tests assert the legacy-like layout and common mojibake fragments.

- Manual QA creates persistent QA records in the local database.
  - Impact: repeated QA runs add products, warehouses, partners, documents, payments, and cash operations.
  - Recommendation: add a test-only cleanup/reset command or run QA against disposable databases.

- Browser-level RU/EN persistence was source-verified, not browser-automated.
  - Impact: low. `localStorage` persistence exists in code, but the in-app browser Node REPL tool was unavailable in this session.
  - Recommendation: verify with browser automation when the tool is available.

## Technical Debt

- The frontend uses a lightweight custom i18n dictionary.
  - Good enough for MVP.
  - Later, consider extracting translation keys by domain and adding a missing-key check in CI.

- API error messages are still backend English strings in many cases.
  - Frontend has translated fallback messages, but server-provided details can remain English.
  - Later, decide whether API errors should be localized in frontend mapping or remain technical.

- Cash balance and partner balances are calculated dynamically.
  - Good enough for MVP correctness and visibility.
  - Later, revisit performance and ledger/register design after legacy rules are known.

## Passed Checks

- Frontend route smoke checks: passed.
- Backend negative accounting scenarios: passed.
- `pytest`: passed.
- `python -m compileall app scripts`: passed.
- `npx tsc -b`: passed.
