import { useMemo, useState, type ReactNode } from "react";
import { useI18n } from "../i18n";

type Column<T> = {
  key: keyof T | string;
  header: string;
  render?: (row: T) => ReactNode;
  sortable?: boolean;
};

type DataTableProps<T> = {
  columns: Column<T>[];
  rows: T[];
  emptyMessage?: string;
  searchable?: boolean;
  pageSize?: number;
};

function cellValue<T extends object>(row: T, key: keyof T | string) {
  return row[key as keyof T];
}

export function DataTable<T extends object>({
  columns,
  rows,
  emptyMessage = "No rows loaded",
  searchable = false,
  pageSize = 25
}: DataTableProps<T>) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const resolvedEmptyMessage = emptyMessage === "No rows loaded" ? t("noRows") : emptyMessage;

  const preparedRows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const filtered = normalizedSearch
      ? rows.filter((row) => Object.values(row).join(" ").toLowerCase().includes(normalizedSearch))
      : rows;
    const sorted = sort
      ? [...filtered].sort((a, b) => {
          const left = String(cellValue(a, sort.key) ?? "");
          const right = String(cellValue(b, sort.key) ?? "");
          return sort.direction === "asc" ? left.localeCompare(right, undefined, { numeric: true }) : right.localeCompare(left, undefined, { numeric: true });
        })
      : filtered;
    return sorted;
  }, [rows, search, sort]);

  const pageCount = Math.max(1, Math.ceil(preparedRows.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const visibleRows = preparedRows.slice(safePage * pageSize, safePage * pageSize + pageSize);

  function toggleSort(column: Column<T>) {
    if (!column.sortable) return;
    const key = String(column.key);
    setSort((current) => current?.key === key && current.direction === "asc" ? { key, direction: "desc" } : { key, direction: "asc" });
  }

  return (
    <div className="panel" style={{ overflowX: "auto" }}>
      {searchable ? (
        <div className="toolbar" style={{ padding: "8px 10px", marginBottom: 0 }}>
          <input className="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder={t("search")} />
        </div>
      ) : null}
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={String(column.key)}
                className={column.sortable ? "sortable" : ""}
                onClick={() => toggleSort(column)}
              >
                {column.header}{sort?.key === String(column.key) ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, index) => (
            <tr key={String("id" in row ? row.id : index)}>
              {columns.map((column) => (
                <td key={String(column.key)}>
                  {column.render ? column.render(row) : String(cellValue(row, column.key) ?? "")}
                </td>
              ))}
            </tr>
          ))}
          {visibleRows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="empty-cell">{resolvedEmptyMessage}</td>
            </tr>
          ) : null}
        </tbody>
      </table>
      {preparedRows.length > pageSize ? (
        <div className="table-footer">
          <span>{safePage + 1} / {pageCount}</span>
          <span>
            <button className="button" disabled={safePage === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>‹</button>
            <button className="button" disabled={safePage >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>›</button>
          </span>
        </div>
      ) : null}
    </div>
  );
}
