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

const CODE_LABEL_KEYS: Record<string, string> = {
  adjustment: "adjustment",
  bank: "bank",
  both: "both",
  cancel: "cancelMovement",
  cancelled: "cancelled",
  cash: "cash",
  cash_in: "cashIn",
  cash_out: "cashOut",
  correction: "correction",
  customer: "customer",
  customer_payment: "customerPayment",
  document: "document",
  draft: "draft",
  incoming: "incoming",
  outgoing: "outgoing",
  payment: "payment",
  post: "postMovement",
  posted: "posted",
  refund: "refund",
  supplier: "supplier",
  supplier_payment: "supplierPayment",
  transfer: "transfer",
};

export function formatCode(value: string | null | undefined, t: (key: never) => string) {
  if (!value) return "";
  return t((CODE_LABEL_KEYS[value] ?? value) as never);
}

export function StatusBadge({ status, label }: { status?: string | null; label?: string }) {
  return <span className={`status-badge ${status ?? "unknown"}`}>{label ?? status ?? ""}</span>;
}
