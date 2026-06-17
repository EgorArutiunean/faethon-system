export function formatDate(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 10);
}

export function formatDateTime(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
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
  cash_operation: "cashOperation",
  correction: "correction",
  create: "create",
  customer: "customer",
  customer_payment: "customerPayment",
  delete: "delete",
  delete_draft: "deleteDraft",
  delete_line: "deleteLine",
  add_line: "addLine",
  document: "document",
  draft: "draft",
  incoming: "incoming",
  import: "importLite",
  "opening-partner-balances": "importOpeningPartnerBalances",
  "opening-stock": "importOpeningStock",
  outgoing: "outgoing",
  partner: "partner",
  payment: "payment",
  post: "postMovement",
  posted: "posted",
  product: "product",
  products: "products",
  partners: "partners",
  refund: "refund",
  supplier: "supplier",
  supplier_payment: "supplierPayment",
  transfer: "transfer",
  update: "update",
  update_header: "updateHeader",
  update_line: "updateLine",
  warehouse: "warehouse",
  warehouses: "warehouses",
};

function prettifyCode(value: string) {
  return value
    .replace(/^post:/, "")
    .replace(/^cancel:/, "")
    .replace(/[-_]/g, " ")
    .trim();
}

export function formatCode(value: string | null | undefined, t: (key: never) => string) {
  if (!value) return "";
  const key = CODE_LABEL_KEYS[value];
  return key ? t(key as never) : prettifyCode(value);
}

export function StatusBadge({ status, label }: { status?: string | null; label?: string }) {
  return <span className={`status-badge ${status ?? "unknown"}`}>{label ?? status ?? ""}</span>;
}
