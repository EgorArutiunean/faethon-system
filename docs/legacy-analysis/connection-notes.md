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
| 2026-05-04 | Legacy utilities found in uploaded project root | `gbak.exe`, `gfix.exe` file version `WI-V6.0.1.6`, product `InterBase Server`, company `Inprise Corporation` | n/a | Runtime identified, connection still not attempted through repair tools | `FUNSTART.BAT` contains `gfix -sweep`, `gfix -mend`, `gbak -R` and must not be run. `Путь.txt` confirms that the legacy app expected a remote InterBase server; the workstation/server name and absolute path are intentionally omitted. No `gds32.dll`, `ibserver.exe`, or `ibguard.exe` was found in the uploaded files. |
| 2026-09-05 | No database engine invoked; filesystem-only safety preparation | SHA-256 verification | n/a | Working copy recreated successfully | `migration/legacy_work/BUY_COPY.GDB` is 523431936 bytes, marked read-only, and has SHA-256 `E63BA2B5C3D088DBF0F8177F3822912FC74B8F4F89D6DA0FD871BFBF499FE8B5`, identical to the source. The source was not opened or modified. Native InterBase client/server files are still unavailable, so metadata export was not attempted. |
| 2026-09-05 | IBSurgeon FirstAID 8.0.505 | Low-level preview tool | n/a | Installed; preview awaiting interactive launch | Official installer downloaded from `ib-aid.com`; SHA-256 `BBB101FCCB43F134C8190B20DE698EFEDD335C347FEBBE27E0E835D62598AE58`; Authenticode signature valid, signer `TOO IBSURGEON SOFTWARE`, GlobalSign. Disposable writable input `BUY_PREVIEW_20260905.GDB` created with a hash identical to the golden copy. The current Codex host exposes no native-app windows, and FirstAID has no documented CLI preview mode, so selecting `Open corrupted database` could not be automated safely. No repair/export action was run. |
| 2026-09-05 | IBSurgeon FirstAID 8.0.505 Preview | Low-level page reader | detected database charset `251` | Success | InterBase 7.1 / ODS 11.1, dialect 1, page size 4096, normal backup state, 127791 total pages, 0 bad pages, 68 relations, 106501 relation data pages and 1 readable generator. The current UI screenshot shows the disposable `BUY_PREVIEW_20260905.GDB`. An earlier FirstAID log recorded opening the original file; its SHA-256 was rechecked afterward and remains unchanged. No DirectFix/repair was used. |
| 2026-09-05 | InterBase 2020 local recovery installation | InterBase server/client | n/a | Blocked before database attach | Installed in a dedicated local recovery directory, but the server reports that the product is not registered. No database connection or export was attempted. Continue only through official Developer Edition registration/licensing. |

## Historical Python/Firebird Discovery Run

Working database copy:

```text
<repo>\migration\legacy_work\BUY_COPY.GDB
```

Copy verification on 2026-09-05:

- size: `523431936` bytes;
- SHA-256: `E63BA2B5C3D088DBF0F8177F3822912FC74B8F4F89D6DA0FD871BFBF499FE8B5`;
- hash matches the original source file;
- Windows read-only attribute: enabled.

Environment file:

```text
<repo>\migration\legacy_discovery\.env
```

Configured values:

- `LEGACY_DB_PATH=<repo>\migration\legacy_work\BUY_COPY.GDB`
- `LEGACY_DB_USER=SYSDBA`
- `LEGACY_DB_PASSWORD=<local-secret>`
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

The Python/Firebird connection did not discover tables. A later FirstAID
read-only preview did identify the following relevant relations:

| Table | Status |
| --- | --- |
| `STOVAR` | Confirmed by preview; product rows and codes are readable |
| `SGRP` | Confirmed by preview; product-group rows are readable |
| `SEDIZM` | Confirmed by preview; 14 unit rows are readable |
| `SPODR` | Relation name confirmed; warehouse/division semantics need export validation |
| `OSTATOK` | Relation name confirmed; not the approved source of opening stock until reconciled |
| `NAKLAD`, `LISTDOK`, `SODDOK` | Relation names confirmed; history is out of migration scope |
| `OPLATA`, `KASBOOK`, `PROVODKA` | Relation names confirmed; history is out of migration scope |
| `LICO` | Confirmed by preview; contains PII/passport fields and must not be exported wholesale |
| `ACCESS` | Relation name confirmed; legacy access mapping remains unverified |

## Portable Client Plan

Use a portable native client instead of installing Firebird system-wide.

Expected location:

```text
<repo>\tools\firebird\fbclient.dll
```

Configured variable:

```dotenv
LEGACY_FIREBIRD_CLIENT=<repo>\tools\firebird\fbclient.dll
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
<repo>\tools\firebird\fbclient.dll
```

Current file details:

- source package: official Firebird 2.1.7 Win64 Embedded zip kit;
- actual binary: `fbembed.dll` copied to `fbclient.dll` for embedded/local loading;
- file version: `WI-V2.1.7.18553`;
- product version: `2.1.7.18553`;
- charset attempted: `WIN1251`;
- local lock directory used during attempts: `<repo>\tools\firebird\lock`.

Additional attempt:

- Firebird 2.5.9 Win64 normal zip kit was downloaded from the official Firebird GitHub release and its `bin\fbclient.dll` was tried first.
- Firebird 2.5.9 Win64 Embedded was also tried, but it supports ODS `11.2`, while `BUY_COPY.GDB` reports `11.1`.

Current conclusion:

- `inspect_firebird.py` did not connect successfully.
- No structured metadata, row-count manifest or versioned sample export was produced.
- FirstAID separately confirmed 68 relations and readable representative rows
  for `STOVAR`, `SGRP`, `SEDIZM`, `CURRENSY` and `LICO`.
- `WIN1251` and `NONE` both fail before any SQL query, so charset is not the current blocker.
- Current portable client is detected and loaded: Firebird `WI-V2.1.7.18553`.
- Uploaded legacy utilities identify the expected engine family as InterBase 6.0.1.6 from Inprise.
- Firebird remains incompatible with this InterBase file. InterBase 2020 is now
  installed locally, but the server is blocked by product registration; this is
  the current blocker to a structured read-only export.
- The remaining gap is a repeatable engine-level export with DDL, full counts,
  typed fields and an auditable allowlist—not proof that the tables exist.

## Troubleshooting Options

The Firebird compatibility path has been exhausted for this InterBase database.
Next steps:

1. Complete official InterBase 2020 Developer Edition registration in an
   isolated recovery environment.
2. Register only a disposable copy; never attach or repair the original/golden copy.
3. Export an allowlisted schema/count manifest and only the required directory fields.
4. Validate Cyrillic text, key uniqueness and counts before transformation.
5. If registration cannot be obtained, request a structured export from an
   authorised operator with a compatible licensed InterBase environment.
