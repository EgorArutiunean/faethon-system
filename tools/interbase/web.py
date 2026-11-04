"""Local read-only browser for the InterBase BUY.GDB copy.

Firebird cannot open this file. The page reads the database directly and
serves it on localhost. Nothing is written back to the file.

    python tools/interbase/web.py
"""

from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from gdb_reader import Database

def default_database() -> Path:
    mounted = Path("/data/BUY.GDB")
    if mounted.is_file():
        return mounted
    return Path(__file__).resolve().parents[2] / "migration" / "legacy_work" / "BUY_COPY.GDB"
PAGE_SIZE = 50

DB: Database | None = None


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def page(title: str, body: str) -> bytes:
    db = DB
    meta = ""
    if db is not None:
        meta = (
            f"ODS {db.ods_major}.{db.ods_minor} · InterBase 7.1 · "
            f"{db.page_size} byte pages · read only"
        )
    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; font: 14px/1.45 "Segoe UI", system-ui, sans-serif; color: #1c1917; background: #f4f1ea; }}
  header {{ background: #1f2933; color: #f8fafc; padding: 16px 24px 14px; }}
  header a {{ color: inherit; text-decoration: none; }}
  header h1 {{ margin: 0 0 4px; font-size: 18px; font-weight: 650; }}
  header p {{ margin: 0; color: #cbd5e1; font-size: 13px; }}
  main {{ padding: 20px 24px 40px; }}
  .note {{ background: #fff7ed; border: 1px solid #fed7aa; color: #9a3412; padding: 10px 12px; border-radius: 8px; margin: 0 0 16px; }}
  .layout {{ display: grid; grid-template-columns: 280px 1fr; gap: 20px; align-items: start; }}
  nav {{ background: white; border: 1px solid #e7e5e4; border-radius: 10px; padding: 8px; max-height: calc(100vh - 140px); overflow: auto; }}
  nav a {{ display: flex; justify-content: space-between; gap: 8px; padding: 6px 8px; border-radius: 6px; color: inherit; text-decoration: none; }}
  nav a:hover, nav a.active {{ background: #f1efe8; }}
  nav .count {{ color: #78716c; font-variant-numeric: tabular-nums; }}
  .panel {{ background: white; border: 1px solid #e7e5e4; border-radius: 10px; padding: 14px; overflow: auto; }}
  form {{ display: flex; gap: 8px; margin: 0 0 12px; }}
  input, button {{ font: inherit; }}
  input {{ flex: 1; border: 1px solid #d6d3d1; border-radius: 8px; padding: 7px 10px; }}
  button, .button {{ background: #1f2933; color: white; border: 0; border-radius: 8px; padding: 7px 12px; text-decoration: none; }}
  table {{ border-collapse: collapse; width: max-content; min-width: 100%; }}
  th, td {{ border-bottom: 1px solid #e7e5e4; padding: 6px 10px; text-align: left; vertical-align: top; white-space: nowrap; }}
  th {{ position: sticky; top: 0; background: #fafaf9; font-size: 12px; }}
  th small {{ display: block; color: #78716c; font-weight: 450; }}
  td.nil {{ color: #a8a29e; }}
  .pager {{ display: flex; gap: 12px; align-items: center; margin-top: 12px; }}
  @media (max-width: 800px) {{ .layout {{ grid-template-columns: 1fr; }} nav {{ max-height: 240px; }} }}
</style>
</head>
<body>
<header>
  <h1><a href="/">BuySell · BUY.GDB</a></h1>
  <p>{esc(meta)}</p>
</header>
<main>
{body}
</main>
</body>
</html>"""
    return document.encode("utf-8")


def table_nav(current: str = "") -> str:
    links = []
    for table in DB.user_tables():
        cls = " class='active'" if table.name == current else ""
        count = f"{table.row_count:,}".replace(",", " ")
        links.append(
            f"<a{cls} href='/table/{quote(table.name)}'><span>{esc(table.name)}</span>"
            f"<span class='count'>{count}</span></a>"
        )
    return "<nav>" + "".join(links) + "</nav>"


def home() -> bytes:
    body = """
<div class="note">This is a read-only view of a local copy. The original BUY.GDB is not opened for writing. The file is InterBase 7.1, which Firebird cannot attach to.</div>
<div class="layout">
""" + table_nav() + """
<div class="panel">
  <p>Choose a table. Counts are the live records found while scanning data pages.</p>
  <p>Text is decoded as Windows-1251. Dates use the InterBase epoch (17 Nov 1858).</p>
</div>
</div>
"""
    return page("BUY.GDB", body)


def table_view(name: str, query: dict[str, list[str]]) -> bytes | None:
    table = DB.table_by_name(name)
    if table is None or table.is_system:
        return None
    offset = _int_arg(query, "offset", 0)
    limit = min(_int_arg(query, "limit", PAGE_SIZE), 200)
    text = (query.get("q") or [""])[0]
    found, more = DB.rows(table, offset=offset, limit=limit, query=text)
    columns = [column for column in table.fields if column.name]
    heads = "".join(f"<th>{esc(column.name)}<small>{esc(column.type_name)}</small></th>" for column in columns)
    body_rows = []
    for row in found:
        cells = []
        for column, value in zip(table.fields, row):
            if not column.name:
                continue
            if value is None or value == "":
                cells.append("<td class='nil'>—</td>")
            else:
                text_value = str(value)
                cells.append(f"<td title='{esc(text_value)}'>{esc(text_value[:180])}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    grid = "<p>No rows on this page.</p>" if not body_rows else f"<table><thead><tr>{heads}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    prev_link = ""
    if offset > 0:
        prev_offset = max(offset - limit, 0)
        prev_link = f"<a class='button' href='/table/{quote(table.name)}?offset={prev_offset}&limit={limit}&q={quote(text)}'>Previous</a>"
    next_link = ""
    if more:
        next_link = f"<a class='button' href='/table/{quote(table.name)}?offset={offset + limit}&limit={limit}&q={quote(text)}'>Next</a>"
    count = f"{table.row_count:,}".replace(",", " ")
    body = f"""
<div class="layout">
{table_nav(table.name)}
<div class="panel">
  <h2 style="margin:0 0 8px">{esc(table.name)}</h2>
  <p style="margin:0 0 12px;color:#57534e">{count} live rows · relation {table.relation_id}</p>
  <form method="get">
    <input type="hidden" name="offset" value="0">
    <input type="hidden" name="limit" value="{limit}">
    <input name="q" value="{esc(text)}" placeholder="Filter text in the scanned rows">
    <button type="submit">Filter</button>
  </form>
  {grid}
  <div class="pager">{prev_link}{next_link}<span>offset {offset}</span></div>
</div>
</div>
"""
    return page(table.name, body)


def _int_arg(query: dict[str, list[str]], key: str, default: int) -> int:
    raw = (query.get(key) or [str(default)])[0]
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, 0)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/tables":
            payload = [
                {"name": table.name, "rows": table.row_count, "columns": [column.name for column in table.fields if column.name]}
                for table in DB.user_tables()
            ]
            self._send(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return
        if path == "/api/rows":
            name = (query.get("table") or [""])[0]
            table = DB.table_by_name(name) if name else None
            if table is None or table.is_system:
                self._send(b'{"error":"unknown table"}', "application/json; charset=utf-8", 404)
                return
            offset = _int_arg(query, "offset", 0)
            limit = min(_int_arg(query, "limit", PAGE_SIZE), 200)
            text = (query.get("q") or [""])[0]
            found, more = DB.rows(table, offset=offset, limit=limit, query=text)
            columns = [column.name for column in table.fields if column.name]
            records = []
            for row in found:
                records.append({column: value for column, value in zip(columns, (value for column, value in zip(table.fields, row) if column.name))})
            payload = {"table": table.name, "offset": offset, "more": more, "rows": records}
            self._send(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            self._send(home(), "text/html; charset=utf-8")
            return
        if path.startswith("/table/"):
            name = path.removeprefix("/table/")
            rendered = table_view(name, query)
            if rendered is None:
                self._send(page("Not found", "<p>That table is not in this database.</p>"), "text/html; charset=utf-8", 404)
                return
            self._send(rendered, "text/html; charset=utf-8")
            return
        self._send(page("Not found", "<p>Not found.</p>"), "text/html; charset=utf-8", 404)

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}")


def serve(database: Path, host: str, port: int) -> None:
    global DB
    print(f"Opening {database}")
    DB = Database(database)
    print(f"Ready: ODS {DB.ods_major}.{DB.ods_minor}, {len(DB.user_tables())} user tables")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Browse http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping")
    finally:
        server.server_close()
        DB.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Browse a copy of BUY.GDB in the browser")
    parser.add_argument("--database", type=Path, default=default_database())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit(f"Database copy not found: {args.database}")
    serve(args.database, args.host, args.port)


if __name__ == "__main__":
    main()
