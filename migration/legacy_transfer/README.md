# Import a reviewed legacy transfer

Run from the repository root with the local PostgreSQL and backend Compose
services running from this checkout. Use a reviewed transfer plan (version 2)
and a separate historical invoice package. Keep these inputs and backups
outside Git.

```sh
python migration/legacy_transfer/run_import.py --plan /path/to/transfer_plan.json --history /path/to/documents_package.json
```

The default run reads PostgreSQL and checks the plan against the target table
fingerprints. If archive tables are absent, it validates the invoice package
without inserting rows.

To apply a reviewed plan, add `--apply --backup-dir /path/to/backups`. The runner
checks a PostgreSQL dump before applying migrations. Catalog cleanup, directory
changes and opening stock run in one transaction. Historical invoices are
loaded separately into the read-only archive without posting operational
movements. Both imports support retrying after a failure. If the target
fingerprints differ, regenerate the plan against the current database.
