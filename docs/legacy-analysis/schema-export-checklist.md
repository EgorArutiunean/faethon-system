# Schema Export Checklist

Use this checklist during legacy discovery.

## Before Running Scripts

- [ ] A copy of `BUY.GDB` exists.
- [ ] `.env` points to the copied database.
- [ ] `LEGACY_CONFIRM_COPY=true` is set.
- [ ] Native Firebird/InterBase client library is installed.
- [ ] Original database is not opened or modified.
- [ ] `FUNSTART.BAT` has not been run.

## Scripts

- [ ] `python inspect_firebird.py` succeeds.
- [ ] `python export_metadata.py` creates `tables.csv`.
- [ ] `python export_metadata.py` creates `columns.csv`.
- [ ] `python export_metadata.py` creates `indexes.csv`.
- [ ] `python export_metadata.py` creates `triggers.sql`.
- [ ] `python export_metadata.py` creates `procedures.sql`.
- [ ] `python export_row_counts.py` creates `row_counts.csv`.
- [ ] `python export_sample_rows.py` creates files under `samples/`.

## Review

- [ ] Key table `TOVAR` is present.
- [ ] Key table `SKLAD` is present.
- [ ] Key table `OSTATOK` is present.
- [ ] Key table `NAKLAD` is present.
- [ ] Key table `LISTDOK` is present.
- [ ] Key table `SODDOK` is present.
- [ ] Key table `OPLATA` is present.
- [ ] Key table `KASSA_BOOK` is present.
- [ ] Key table `PROVODKA` is present.
- [ ] Key table `LICO` is present.
- [ ] Key table `ACCESS` is present.
- [ ] Trigger sources are readable.
- [ ] Procedure sources are readable.
- [ ] Row counts look plausible.
- [ ] Sample rows do not reveal unexpected encoding problems.

## If Something Fails

Document the failure in `connection-notes.md` and do not modify the original database.
