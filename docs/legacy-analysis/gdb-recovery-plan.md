# BUY.GDB directory recovery plan

Date: 2026-09-05

## Finding

The file reports ODS 11.1. This number is shared by InterBase 7.1 and Firebird
2.1, but the post-InterBase-6 product lines are not file-compatible. The prior
Firebird 2.1 error (`found 11.1, support 11.1`) is therefore consistent with an
InterBase 7.1 database and is not evidence that another Firebird 2.1 package
will open it. The adjacent `gbak.exe` version 6.0.1.6 is older than the likely
database format and is not sufficient without a matching server.

## Goal and scope

Recover directories/reference data only:

- products, SKU/legacy names, groups and units;
- warehouses;
- customers/suppliers and their type;
- prices, currencies and referenced classifiers where present.

`LICO` contains personal data (observed fields include birth dates, names,
passport numbers and issuing authority). Do not export the whole table. If a
business partner mapping genuinely needs a person name, create a local
data-minimised projection after identifying the relationship; exclude birth
dates, passport data and issuing authority. Never use these rows in demo or
portfolio data.

Do not migrate historical documents, payments, cash entries or postings.

## Safety model

1. Keep `migration/legacy_work/BUY_COPY.GDB` as an immutable golden copy.
2. Before each tool attempt, clone it to a new disposable file.
3. Never run `FUNSTART.BAT`, `gfix -mend`, `gfix -sweep`, `gbak -R` or an
   in-place recovery operation on the source or golden copy.
4. Run legacy engines in an isolated VM with no inbound network access.
5. Preserve tool/version logs and SHA-256 hashes for every input/output.
6. Export only to CSV/SQL/new database files; validate counts and samples before
   transforming data.

## Route A — recommended: InterBase 2020 Developer Edition

InterBase documentation states that InterBase 2020 can back up ODS 11 and ODS
12 databases with `gbak` in client/server mode. The free Developer Edition is
licensed for non-production development on a single local computer.

Procedure:

1. Obtain the official InterBase 2020 installer through Embarcadero Product
   Downloads / Previous Releases. Do not substitute current InterBase 15: it
   supports only newer ODS versions for direct connection.
2. Current state: InterBase 2020 has been installed in a dedicated local
   recovery directory. The server is blocked by product registration, so no
   database attach or export has been performed. Resolve the official Developer
   Edition registration before continuing; an isolated Windows VM remains the
   preferred execution environment for the actual recovery run.
3. Copy the golden GDB to a disposable writable file inside the VM.
4. Start the InterBase server and register/alias only the disposable path.
5. Use the InterBase 2020 `gbak` executable in client/server mode to create a
   logical backup from the disposable database. Do not use service-manager mode.
6. Restore that backup into a new InterBase 2020 database.
7. Connect to the restored database and export metadata, table counts and the
   required directories using read-only SQL transactions.
8. Compare counts, key uniqueness and representative Cyrillic values.

The disposable database may be upgraded or changed on attach. This is acceptable
only because the golden copy remains immutable.

## Route B — fastest compatibility probe: IBSurgeon FirstAID 8

IBSurgeon FirstAID 8 explicitly supports InterBase 7.1. Its free preview can
inspect whether table data is visible without requiring a successful database
engine attach.

Procedure:

1. Obtain FirstAID 8 only from the IBSurgeon website.
2. Open a disposable copy, never the golden copy.
3. Use Preview only; do not choose DirectFix or repair operations.
4. Confirm that expected directory tables and readable WIN1251 text are visible.
5. If preview works, either license extraction or return to Route A for a logical
   backup/export. Because only directories are needed, request a scoped export
   rather than full database repair.

## Route C — specialist extraction

If both routes fail, send an encrypted disposable copy to an InterBase recovery
specialist under a data-processing agreement. Request CSV plus:

- table and column metadata;
- row count per exported table;
- primary/natural key description;
- encoding used;
- SHA-256 of the received copy and exported archive;
- exception/corruption report.

Do not ask for in-place database repair; ask for read-only/scoped extraction of
reference tables.

## Acceptance criteria

- original and golden-copy SHA-256 remain
  `E63BA2B5C3D088DBF0F8177F3822912FC74B8F4F89D6DA0FD871BFBF499FE8B5`;
- metadata and row counts are exported;
- product, group, unit, warehouse and partner tables are identified;
- Cyrillic samples decode correctly (try WIN1251, then metadata-declared charset);
- duplicate/null/orphan statistics are recorded;
- canonical Import Lite files pass dry-run;
- no historical transaction data is included in the migration package.
