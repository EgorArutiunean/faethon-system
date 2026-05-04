# Role-Based QA

Date: 2026-05-02

Scope: Simple Auth & Permissions smoke QA for current MVP roles. No Reports/Export/Print Forms work was added.

## Demo Users

| Email | Password | Role |
| --- | --- | --- |
| `admin@example.com` | `admin123` | `admin` |
| `manager@example.com` | `manager123` | `manager` |
| `cashier@example.com` | `cashier123` | `cashier` |
| `viewer@example.com` | `viewer123` | `viewer` |

`seed_demo.py` creates or updates these users and resets their demo passwords on each seed run.

## Permission Matrix

| Area / Action | Admin | Manager | Cashier | Viewer |
| --- | --- | --- | --- | --- |
| Products read | Yes | Yes | No | Yes |
| Products create/update | Yes | Yes | No | No |
| Warehouses read | Yes | Yes | No | Yes |
| Warehouses create/update | Yes | Yes | No | No |
| Partners read | Yes | Yes | Yes | Yes |
| Partners create/update | Yes | Yes | No | No |
| Documents read | Yes | Yes | No | Yes |
| Documents create/update | Yes | Yes | No | No |
| Documents post/cancel | Yes | Yes | No | No |
| Stock read | Yes | Yes | No | Yes |
| Payments read | Yes | No | Yes | Yes |
| Payments create/post/cancel | Yes | No | Yes | No |
| Cash read | Yes | No | Yes | Yes |
| Cash create/cancel | Yes | No | Yes | No |
| Reports read | Yes | Yes | Yes | Yes |
| Settings/users manage | Yes | No | No | No |

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
- Can create payments.
- Can create cash operations.
- Document posting returns HTTP 403.

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

## Findings

No P0/P1 role-permission defects were found during this pass.

P2 / follow-up:

- Add automated browser-level role tests when the frontend E2E test harness is introduced.
- Keep role labels and permission wording aligned with BuySell terminology as screens evolve.

## Result

Role-based API smoke passed for all four demo roles. Frontend route/action restrictions match the current permission model at source level. Existing backend and frontend checks pass.
