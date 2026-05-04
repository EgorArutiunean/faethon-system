# Connection Notes

Use this file to record attempts to connect to a copy of `BUY.GDB`.

## Safety Rules

- Work only with a copied database file.
- Do not run `FUNSTART.BAT`.
- Do not run `gfix -mend`, `gfix -sweep`, `gbak -R`, or any write/repair action on the original database.
- Keep the original `BUY.GDB` unchanged.

## Attempt Log

| Date | Client | Driver | Charset | Result | Error / Notes |
| --- | --- | --- | --- | --- | --- |
| 2026-05-01 | No native Firebird/InterBase client found in PATH | Python 3.13.1, `fdb 2.0.4`, `firebird-driver 1.10.11` installed | WIN1251 | Failed before database open | `fdb connection failed: The location of Firebird Client Library could not be determined.` |
| 2026-05-01 | Chocolatey `firebird 5.0.4` install attempt | n/a | n/a | Failed to install client | Chocolatey was not elevated and failed on lock/access under `C:\ProgramData\chocolatey\lib...`; no `fbclient.dll`, `gds32.dll`, or `fbembed.dll` became available. |
| 2026-05-01 | Firebird 2.5.9 Win64 `fbclient.dll` from official GitHub zip kit | `fdb 2.0.4` | WIN1251 | Failed | `SQLCODE: -904 - unavailable database`; ordinary client DLL requires a running local/server Firebird instance for this file path. |
| 2026-05-01 | Firebird 2.5.9 Win64 Embedded, `fbembed.dll` copied as `tools/firebird/fbclient.dll` | `fdb 2.0.4` | WIN1251 | Failed | First required local `FIREBIRD_LOCK`; after running outside sandbox: `unsupported on-disk structure ... found 11.1, support 11.2`. |
| 2026-05-01 | Firebird 2.1.7 Win64 Embedded, `fbembed.dll` copied as `tools/firebird/fbclient.dll` | `fdb 2.0.4` | WIN1251 | Failed before database open | `function 'fb_shutdown_callback' not found`; modern `fdb 2.0.4` expects a newer client API. |
| 2026-05-01 | Firebird 2.1.7 Win64 Embedded, `fbembed.dll` copied as `tools/firebird/fbclient.dll` | locally patched/installed `fdb 1.8` | WIN1251 | Failed | `unsupported on-disk structure ... found 11.1, support 11.1`. This suggests the file is not readable by Firebird 2.1 despite the same displayed ODS number, likely due to InterBase/implementation compatibility. |
| 2026-05-04 | Firebird 2.1.7 Win64 Embedded, `fbembed.dll` copied as `tools/firebird/fbclient.dll` | `fdb` through `inspect_firebird.py` | WIN1251 | Failed | `SQLCODE: -820 - unsupported on-disk structure for file ... BUY_COPY.GDB; found 11.1, support 11.1`. Client DLL was found and loaded; failure happens at database open. |
| 2026-05-04 | Firebird 2.1.7 Win64 Embedded, same DLL | `fdb` through `inspect_firebird.py` | NONE | Failed | Same `SQLCODE: -820 ... found 11.1, support 11.1`; charset is not the blocker. |
| 2026-05-04 | Firebird 2.5.9 Win64 `gstat.exe` from official zip kit | `gstat -h` read-only header attempt | n/a | Failed | `Wrong ODS version, expected 11, encountered 11`. No repair/sweep/restore was run. |
| 2026-05-04 | Legacy utilities found in uploaded project root | `gbak.exe`, `gfix.exe` file version `WI-V6.0.1.6`, product `InterBase Server`, company `Inprise Corporation` | n/a | Runtime identified, connection still not attempted through repair tools | `FUNSTART.BAT` contains `gfix -sweep`, `gfix -mend`, `gbak -R` and must not be run. `Путь.txt` contains `SERGEY:D:\Buy\BUY.GDB`, which indicates the legacy app expected an InterBase server on host `SERGEY`. No `gds32.dll`, `ibserver.exe`, or `ibguard.exe` was found in the uploaded files. |

## Current Discovery Run

Working database copy:

```text
C:\Users\Egor\Buy\buy-modern\migration\legacy_work\BUY_COPY.GDB
```

Environment file:

```text
C:\Users\Egor\Buy\buy-modern\migration\legacy_discovery\.env
```

Configured values:

- `LEGACY_DB_PATH=C:\Users\Egor\Buy\buy-modern\migration\legacy_work\BUY_COPY.GDB`
- `LEGACY_DB_USER=SYSDBA`
- `LEGACY_DB_PASSWORD=masterkey`
- `LEGACY_DB_CHARSET=WIN1251`
- `LEGACY_CONFIRM_COPY=true`
- `LEGACY_OUTPUT_DIR=migration/legacy_schema`
- `LEGACY_SAMPLE_LIMIT=50`

Commands run:

```powershell
python -m pip install -r .\requirements.txt
python .\inspect_firebird.py
```

Dependency install result:

- first attempt failed because sandboxed networking blocked access to PyPI;
- second attempt with approval succeeded;
- installed `fdb 2.0.4`, `firebird-driver 1.10.11`, `firebird-base 1.8.0`, `python-dateutil 2.9.0.post0`, `protobuf 7.34.1`, `six 1.17.0`.

Connection result:

```text
Connection failed.
fdb connection failed: The location of Firebird Client Library could not be determined.
Try an older Firebird 1.5/2.0 client or the original InterBase client if this is an old ODS database.
```

Files exported:

- none from the database yet;
- `migration/legacy_schema/` currently contains only placeholder `.gitkeep` files.

Tables discovered:

- none, because connection did not reach the database.

Key table presence:

| Table | Status |
| --- | --- |
| `TOVAR` | Not checked: no database connection |
| `SKLAD` | Not checked: no database connection |
| `OSTATOK` | Not checked: no database connection |
| `NAKLAD` | Not checked: no database connection |
| `LISTDOK` | Not checked: no database connection |
| `SODDOK` | Not checked: no database connection |
| `OPLATA` | Not checked: no database connection |
| `KASSA_BOOK` | Not checked: no database connection |
| `PROVODKA` | Not checked: no database connection |
| `LICO` | Not checked: no database connection |
| `ACCESS` | Not checked: no database connection |

## Portable Client Plan

Use a portable native client instead of installing Firebird system-wide.

Expected location:

```text
C:\Users\Egor\Buy\buy-modern\tools\firebird\fbclient.dll
```

Configured variable:

```dotenv
LEGACY_FIREBIRD_CLIENT=C:\Users\Egor\Buy\buy-modern\tools\firebird\fbclient.dll
```

Version order:

1. Try Firebird 2.5.x Win64 first.
2. If the database does not open, try Firebird 2.1 or 2.0 client.
3. If it still does not open, try Firebird 1.5 client.
4. Last resort: use the original InterBase 6 client.

Use only official Firebird release packages or trusted InterBase client files. Do not use random DLL download sites. Do not modify Chocolatey lock files just to complete this discovery run.

## Portable Client Files Currently Present

Final `fbclient.dll` path:

```text
C:\Users\Egor\Buy\buy-modern\tools\firebird\fbclient.dll
```

Current file details:

- source package: official Firebird 2.1.7 Win64 Embedded zip kit;
- actual binary: `fbembed.dll` copied to `fbclient.dll` for embedded/local loading;
- file version: `WI-V2.1.7.18553`;
- product version: `2.1.7.18553`;
- charset attempted: `WIN1251`;
- local lock directory used during attempts: `C:\Users\Egor\Buy\buy-modern\tools\firebird\lock`.

Additional attempt:

- Firebird 2.5.9 Win64 normal zip kit was downloaded from the official Firebird GitHub release and its `bin\fbclient.dll` was tried first.
- Firebird 2.5.9 Win64 Embedded was also tried, but it supports ODS `11.2`, while `BUY_COPY.GDB` reports `11.1`.

Current conclusion:

- `inspect_firebird.py` did not connect successfully.
- No metadata, row counts, or samples were exported.
- `WIN1251` and `NONE` both fail before any SQL query, so charset is not the current blocker.
- Current portable client is detected and loaded: Firebird `WI-V2.1.7.18553`.
- Uploaded legacy utilities identify the expected engine family as InterBase 6.0.1.6 from Inprise.
- The blocker is database engine/ODS compatibility and missing original InterBase client/server runtime (`gds32.dll`/`ibserver.exe`/`ibguard.exe`).
- Key tables are still not verified from a live database connection.

Current key table status:

| Table | Status |
| --- | --- |
| `TOVAR` | Not checked: connection failed |
| `SKLAD` | Not checked: connection failed |
| `OSTATOK` | Not checked: connection failed |
| `NAKLAD` | Not checked: connection failed |
| `LISTDOK` | Not checked: connection failed |
| `SODDOK` | Not checked: connection failed |
| `OPLATA` | Not checked: connection failed |
| `KASSA_BOOK` | Not checked: connection failed |
| `PROVODKA` | Not checked: connection failed |
| `LICO` | Not checked: connection failed |
| `ACCESS` | Not checked: connection failed |

## Troubleshooting Options

If the Python scripts cannot connect:

1. Put Firebird 2.5.x Win64 `fbclient.dll` in `buy-modern/tools/firebird/`.
2. Try Firebird 2.1/2.0 client libraries.
3. Try Firebird 1.5 or InterBase 6.x client libraries for old ODS compatibility.
4. Try connecting through a local Firebird/InterBase server instead of embedded/direct file access.
5. Try charset `WIN1251`, then `NONE` if metadata reads fail.
6. Confirm that `LEGACY_DB_PATH` points to a copied database, not the original.
