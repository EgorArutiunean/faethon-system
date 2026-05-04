# Full Smoke

Date: 2026-05-04

Environment:

- Docker Compose production stack: `docker-compose.prod.yml`
- Database: PostgreSQL container
- Frontend/nginx: `http://localhost`
- API: `http://localhost/api/v1`

Container status:

- `buy-modern-postgres-1`: healthy
- `buy-modern-backend-1`: healthy
- `buy-modern-frontend-1`: healthy

## Commands Used

```powershell
docker compose --env-file .env.production -f docker-compose.prod.yml ps
Invoke-WebRequest -UseBasicParsing http://localhost/health
```

The smoke scenario was executed against the production nginx/API endpoint at `http://localhost`.

Final verification commands:

```powershell
pytest
python -m compileall app scripts
npx tsc -b
```

## Passed

- Login admin: `admin@example.com / admin123`.
- Logout behavior: simulated by clearing token; protected API request without token returns `401`.
- Frontend opened at `/`.
- Frontend routes opened through SPA fallback:
  - `/products`
  - `/documents`
  - `/stock`
  - `/payments`
  - `/cash`
  - `/reports`
  - `/settings`
- Products:
  - created smoke product;
  - product appears in API list;
  - search/sort support verified at DataTable/source level and route smoke level.
- Warehouses:
  - created smoke warehouse.
- Partners:
  - created smoke partner;
  - balance endpoint returned expected zero initial balance;
  - statement endpoint returned successfully.
- Documents:
  - created incoming document;
  - added product line;
  - posted document;
  - printed document form;
  - cancelled document.
- Stock:
  - balance reflected posted incoming document quantity;
  - movements returned document movements.
- Payments:
  - created payment;
  - posted payment;
  - cancelled payment.
- Cash:
  - cash balance endpoint returned successfully;
  - cash book returned rows;
  - manual cash operation created.
- Reports:
  - Stock balances tab/filter endpoint passed;
  - Stock movements tab/filter endpoint passed;
  - Partner debts tab/filter endpoint passed;
  - Cash book tab/filter endpoint passed;
  - Documents register tab/filter endpoint passed.
- Export:
  - XLSX export returned a valid XLSX payload;
  - CSV export returned UTF-8 BOM CSV payload.
- Import Lite:
  - template download returned XLSX;
  - products dry-run accepted a valid test CSV;
  - products apply created a product from test CSV.
- Role-based access quick smoke:
  - viewer can read products and cannot create products;
  - cashier can read cash book and cannot post documents;
  - manager can read stock balances and cannot create cash operations.

Total smoke checks: 42 passed.

## Not Passed

None.

## Bugs

P0:

- None.

P1:

- None.

P2:

- None found during this smoke.

## Fixed

No fixes were required. The smoke did not find P0/P1 issues.

## Notes

- This smoke used real Docker/PostgreSQL services through production nginx.
- Browser route availability was checked through HTTP responses.
- Detailed UI click automation was not used in this pass; operator-critical behavior was verified through authenticated API calls and frontend route smoke.
