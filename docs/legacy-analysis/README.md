# Legacy Analysis

This folder stores findings from the first discovery phase for the old BuySell system.

Read-only access to a copy of `BUY.GDB` is the `legacy` Compose service. Install and run steps are in the root `README.md` and `AGENTS.md`. Firebird clients cannot open this InterBase 7.1 file.

The current phase is limited to:

- inventory of legacy files;
- safe connection notes for a copy of `BUY.GDB`;
- metadata export from the legacy database;
- row counts;
- sample rows from key tables;
- notes about triggers, procedures, and hidden business rules.

Do not design the final PostgreSQL schema here yet. First capture what exists.
