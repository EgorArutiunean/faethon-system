# Role-Based QA

Date: 2026-07-24

Scope: Simple Auth & Permissions smoke QA for current MVP roles. No Reports/Export/Print Forms work was added.

## Demo Users

| Email | Password | Role |
| --- | --- | --- |
| `admin@example.com` | `admin123` | `admin` |
| `manager@example.com` | `manager123` | `manager` |
| `cashier@example.com` | `cashier123` | `cashier` |
| `logist@example.com` | `logist123` | `logist` |
| `viewer@example.com` | `viewer123` | `viewer` |

`seed_demo.py` creates or updates these users and resets their demo passwords on each seed run.
The logistics demo user is assigned to the demo main and retail warehouses.

## Permission Matrix

| Area / Action | Admin | Manager | Cashier | Logist | Viewer |
| --- | --- | --- | --- | --- | --- |
| Products read | Yes | Yes | No | No | Yes |
| Products create/update | Yes | Yes | No | No | No |
| Warehouses read | Yes | Yes | No | No | Yes |
| Warehouses create/update | Yes | Yes | No | No | No |
| Partners read | Yes | Yes | Yes | No | Yes |
| Partners create/update | Yes | Yes | No | No | No |
| Documents read | Yes | Yes | Yes | Assigned warehouses, safe view | Yes |
| Documents create/update | Yes | Yes | No | No | No |
| Documents post/cancel | Yes | Yes | No | No | No |
| Stock read | Yes | Yes | No | No | Yes |
| Payments read | Yes | No | Yes | No | Yes |
| Payments create/post/cancel | Yes | No | Yes | No | No |
| Cash read | Yes | No | Yes | No | Yes |
| Cash create/cancel | Yes | No | Yes | No | No |
| Reports read | Yes | Yes | Yes | No | Yes |
| Logistics read | Yes | No | No | Assigned warehouses | No |
| Purchase cost/currency/rate | Yes | Yes | No | No | No |
| Settings/users manage | Yes | No | No | No | No |

## API Smoke Checked

Admin:

- Login and `/auth/me` return role `admin`.
- Can read and create products.
- Can create cash operations.
- Existing tests cover admin document posting.

Manager:

- Login and `/auth/me` return role `manager`.
- Can read and create products.
- Can read stock balances.
- Cash create returns HTTP 403.
- Settings/users management is not granted.

Cashier:

- Login and `/auth/me` return role `cashier`.
- Can read partners.
- Can read documents for linking payments, but cannot change or post them.
- Can create payments.
- Can create cash operations.
- Document posting returns HTTP 403.

Logist:

- Login and `/auth/me` return role `logist` and assigned warehouses.
- Can read logistics documents only when a source or destination warehouse is assigned.
- Receives sales price and sales total, but not purchase price, cost, purchase currency, or exchange rate.
- Cannot use the ordinary documents API or create, post, and cancel documents.
- A logistics user cannot be created without at least one assigned warehouse.
- The `logist` role cannot be combined with another role.

Viewer:

- Login and `/auth/me` return role `viewer`.
- Can read products, warehouses, partners, documents, stock balances, payments, and cash operations.
- Product create returns HTTP 403.
- Document post returns HTTP 403.
- Cash create returns HTTP 403.

Expected auth failures remain in place:

- Missing token returns HTTP 401.
- Missing permission returns HTTP 403.

## Frontend Smoke Checked

Verified by route/source smoke against the current frontend implementation:

- Login route exists and is wrapped by the auth provider.
- Protected routes require authentication.
- Token is stored in `localStorage` as `buy-modern-token`.
- Logout removes the token and clears current user state.
- Header shows current user email and role.
- Settings navigation is visible only with `settings.manage`.
- Document post action is disabled without `documents.post`.
- Payment post action is disabled without `payments.post`.
- Cash operation creation is disabled without `cash.create`.
- Logistics navigation is visible only with `logistics.read`.
- The logistics screen contains sales-price columns and no purchase-price, currency, or exchange-rate columns.

## Findings

No P0/P1 role-permission defects were found during this pass.

P2 / follow-up:

- Add write workflows only after receipt, picking, transfer, and inventory confirmation rules are approved.
- Keep role labels and permission wording aligned with BuySell terminology as screens evolve.

## Result

Role-based API smoke passed for all five demo roles. `LOG-01` verifies the logistics boundary through the real frontend, API, and PostgreSQL. Existing backend and frontend checks pass.
