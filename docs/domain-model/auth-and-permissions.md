# Auth And Permissions

This MVP uses a simple object/action permission model inspired by Salesforce CRUD permissions, but without Salesforce platform complexity.

## Scope

Implemented:

- email/password login;
- JWT access token;
- current user endpoint;
- password hashing with PBKDF2;
- role-based permission assignment;
- API dependencies returning `401` without token and `403` without permission;
- frontend route guard and logout by deleting the token.

Not implemented:

- role hierarchy;
- sharing rules;
- field-level security;
- permission sets;
- approval workflows;
- record-level sharing.

## Demo Admin

The seed script creates a demo-only admin user:

- email: `admin@example.com`
- password: `admin123`
- role: `admin`

This account is for local development only and must be changed before any real deployment.

## Roles

- `admin`: all permissions;
- `manager`: products, warehouses, partners, documents, stock, reports;
- `cashier`: partner read, payments, cash, reports read;
- `viewer`: read-only access to main operational objects.

## Permissions

Products:

- `products.read`
- `products.create`
- `products.update`
- `products.delete`

Warehouses:

- `warehouses.read`
- `warehouses.create`
- `warehouses.update`
- `warehouses.delete`

Partners:

- `partners.read`
- `partners.create`
- `partners.update`
- `partners.delete`

Documents:

- `documents.read`
- `documents.create`
- `documents.update`
- `documents.post`
- `documents.cancel`

Stock:

- `stock.read`

Payments:

- `payments.read`
- `payments.create`
- `payments.post`
- `payments.cancel`

Cash:

- `cash.read`
- `cash.create`
- `cash.cancel`

System:

- `reports.read`
- `users.manage`
- `settings.manage`

## Frontend Behavior

The frontend uses `AuthContext`:

- stores JWT in `localStorage`;
- loads `/api/v1/auth/me`;
- exposes `can(permission)`;
- redirects unauthenticated users to Login;
- hides Settings when `settings.manage` is absent;
- disables posting/cancellation and cash actions when permissions are absent.

## Legacy Notes

BuySell terminology remains visible in the product:

- products/goods;
- warehouses;
- documents/invoices;
- payments;
- cash;
- partners;
- reports.

TODO LEGACY_RULE_REQUIRED: confirm whether legacy users map to roles directly or require a migration table from old access flags.
