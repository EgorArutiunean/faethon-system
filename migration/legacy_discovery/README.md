# Legacy Discovery Tools

These scripts are for the first phase only: read-only discovery of the old `BUY.GDB` InterBase/Firebird database.

Do not use these scripts against the original production database. Make a file copy first and point `LEGACY_DB_PATH` to that copy. Do not run `FUNSTART.BAT`; it can repair, backup, rename, and restore the database.

## Use the Docker reader

This file is InterBase 7.1 (ODS 11.1). Firebird cannot open it. Do not try another Firebird client.

Copy `miscelanious/BUY.GDB` to `migration/legacy_work/BUY_COPY.GDB`, mark that copy read-only, and run `make legacy`. The browser is `http://127.0.0.1:8765`. Details are in the root `README.md` and `AGENTS.md`.

## Historical client attempts

These clients were tried and failed. Do not repeat them:

1. Firebird 2.5 client tools/libraries.
2. Firebird 2.1 or 2.0 client tools/libraries.
3. Firebird 1.5 client tools/libraries.
4. Original InterBase 6.x client libraries.

The setup below is the failed Firebird-client experiment. Leave it unused. Do not download client DLLs for this file.

## Setup

From `buy-modern/migration/legacy_discovery`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.env .env
```

Edit `.env`.

Required variables:

- `LEGACY_DB_PATH`: path to a copy of `BUY.GDB`.
- `LEGACY_DB_USER`: usually `SYSDBA`.
- `LEGACY_DB_PASSWORD`: current password; the old script shows `masterkey`.
- `LEGACY_DB_CHARSET`: start with `WIN1251` for this Russian-language database.
- `LEGACY_CONFIRM_COPY`: must be `true`.

Optional variables:

- `LEGACY_DB_HOST`: set only for server-style connection, for example `localhost`.
- `LEGACY_DB_ROLE`: role name if required.
- `LEGACY_FIREBIRD_CLIENT`: full path to a portable `fbclient.dll`. If empty, the driver uses the system `PATH`/default loader.
- `LEGACY_OUTPUT_DIR`: defaults to `migration/legacy_schema` under `buy-modern`.
- `LEGACY_SAMPLE_LIMIT`: defaults to `50`.

Example `.env` with portable client:

```dotenv
LEGACY_DB_PATH=C:\Users\Egor\Buy\buy-modern\migration\legacy_work\BUY_COPY.GDB
LEGACY_DB_HOST=
LEGACY_DB_USER=SYSDBA
LEGACY_DB_PASSWORD=masterkey
LEGACY_DB_CHARSET=WIN1251
LEGACY_DB_ROLE=
LEGACY_FIREBIRD_CLIENT=C:\Users\Egor\Buy\buy-modern\tools\firebird\fbclient.dll
LEGACY_CONFIRM_COPY=true
LEGACY_OUTPUT_DIR=migration/legacy_schema
LEGACY_SAMPLE_LIMIT=50
```

## Run

Check connection:

```powershell
python inspect_firebird.py
```

Export tables, columns, indexes, triggers, and procedures:

```powershell
python export_metadata.py
```

Export row counts for user tables:

```powershell
python export_row_counts.py
```

Export sample rows from key tables:

```powershell
python export_sample_rows.py
```

Outputs are written to:

```text
buy-modern/
  migration/
    legacy_schema/
      tables.csv
      columns.csv
      indexes.csv
      triggers.sql
      procedures.sql
      row_counts.csv
      samples/
```

## If Connection Fails

Record the exact error in `docs/legacy-analysis/connection-notes.md`.

Likely causes:

- no native Firebird/InterBase client library in `LEGACY_FIREBIRD_CLIENT` or `PATH`;
- client library is too new for the database ODS version;
- database needs to be accessed through a running old Firebird/InterBase server;
- database file is locked or not a clean copy;
- wrong charset, user, password, or role.

Do not repair, sweep, mend, or restore the original database while troubleshooting.
