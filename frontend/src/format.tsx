export function formatDate(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 10);
}

export function formatMoney(value?: string | number | null) {
  if (value === undefined || value === null || value === "") return "";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return String(value);
  return numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function StatusBadge({ status }: { status?: string | null }) {
  return <span className={`status-badge ${status ?? "unknown"}`}>{status ?? ""}</span>;
}
