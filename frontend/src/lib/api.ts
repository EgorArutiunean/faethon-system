const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export type Product = {
  id: number;
  sku?: string | null;
  name: string;
  base_price?: string | null;
  is_active: boolean;
};

export type Partner = {
  id: number;
  code?: string | null;
  name: string;
  partner_type: "customer" | "supplier" | "both";
  phone?: string | null;
  is_active: boolean;
};

export type Warehouse = {
  id: number;
  code?: string | null;
  name: string;
  address?: string | null;
};

export type DocumentLine = {
  id: number;
  document_id: number;
  product_id: number;
  product_name?: string | null;
  quantity: string;
  price: string;
  line_total: string;
};

export type Document = {
  id: number;
  document_type: string;
  number?: string | null;
  document_date: string;
  status: string;
  partner_id?: number | null;
  partner_name?: string | null;
  warehouse_id?: number | null;
  warehouse_name?: string | null;
  total_amount: string;
  note?: string | null;
  lines?: DocumentLine[];
};

export type StockBalance = {
  id: number;
  product_id: number;
  product_name?: string | null;
  warehouse_id: number;
  warehouse_name?: string | null;
  quantity: string;
};

export type StockMovement = {
  id: number;
  product_id: number;
  product_name?: string | null;
  warehouse_id: number;
  warehouse_name?: string | null;
  document_id?: number | null;
  document_number?: string | null;
  movement_type?: string | null;
  quantity_delta: string;
  reason?: string | null;
  created_at: string;
};

export type Payment = {
  id: number;
  partner_id: number;
  partner_name?: string | null;
  document_id?: number | null;
  document_number?: string | null;
  payment_date: string;
  payment_type: string;
  status: string;
  amount: string;
  method?: string | null;
  note?: string | null;
  cash_operation_id?: number | null;
  cash_operation_status?: string | null;
};

export type PartnerBalance = {
  partner_id: number;
  partner_name: string;
  partner_type: "customer" | "supplier" | "both";
  balance: string;
};

export type PartnerStatementRow = {
  date: string;
  source_type: string;
  source_id: number;
  source_number?: string | null;
  debit: string;
  credit: string;
  balance: string;
  status: string;
};

export type CashOperation = {
  id: number;
  operation_date: string;
  operation_type: string;
  direction: string;
  status: string;
  amount: string;
  partner_id?: number | null;
  partner_name?: string | null;
  document_id?: number | null;
  payment_id?: number | null;
  payment_status?: string | null;
  note?: string | null;
};

export type CashBalance = {
  balance: string;
};

export type CashBookRow = CashOperation & {
  balance: string;
};

export type ReportResponse<T> = {
  rows: T[];
};

export type StockBalanceReportRow = Omit<StockBalance, "id">;

export type StockBalancesReport = ReportResponse<StockBalanceReportRow> & {
  total_quantity: string;
};

export type StockMovementsReport = ReportResponse<StockMovement> & {
  total_quantity: string;
};

export type PartnerDebtsReport = ReportResponse<PartnerBalance> & {
  total_partner_debt: string;
};

export type CashBookReportRow = CashOperation & {
  cash_balance: string;
};

export type CashBookReport = ReportResponse<CashBookReportRow> & {
  cash_in_total: string;
  cash_out_total: string;
  cash_balance: string;
};

export type DocumentsRegisterReportRow = {
  id: number;
  document_number?: string | null;
  document_date: string;
  document_type: string;
  status: string;
  partner_id?: number | null;
  partner_name?: string | null;
  warehouse_id?: number | null;
  warehouse_name?: string | null;
  total_amount: string;
};

export type DocumentsRegisterReport = ReportResponse<DocumentsRegisterReportRow> & {
  total_amount: string;
};

export type CurrentUser = {
  id: number;
  email: string;
  full_name?: string | null;
  role_names: string[];
  permissions: string[];
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type ImportIssue = {
  row: number;
  field?: string | null;
  message: string;
};

export type ImportSummary = {
  rows_total: number;
  rows_valid: number;
  rows_invalid: number;
  errors: ImportIssue[];
  warnings: ImportIssue[];
  applied: boolean;
  created: number;
  skipped: number;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("buy-modern-token");
  const { headers, ...rest } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers ?? {})
    },
    ...rest
  });
  if (!response.ok) {
    const raw = await response.text();
    let detail = raw;
    try {
      const parsed = JSON.parse(raw);
      detail = typeof parsed.detail === "string" ? parsed.detail : raw;
    } catch {
      detail = raw;
    }
    throw new Error(`API request failed: ${response.status} ${detail}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function download(path: string): Promise<Blob> {
  const token = localStorage.getItem("buy-modern-token");
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(`API request failed: ${response.status} ${raw}`);
  }
  return response.blob();
}

export const api = {
  login: (payload: { email: string; password: string }) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request<CurrentUser>("/auth/me"),
  products: () => request<Product[]>("/products"),
  createProduct: (payload: Partial<Product>) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(payload) }),
  updateProduct: (id: number, payload: Partial<Product>) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteProduct: (id: number) => request<void>(`/products/${id}`, { method: "DELETE" }),
  partners: (params = "") => request<Partner[]>(`/partners${params}`),
  createPartner: (payload: Partial<Partner>) =>
    request<Partner>("/partners", { method: "POST", body: JSON.stringify(payload) }),
  updatePartner: (id: number, payload: Partial<Partner>) =>
    request<Partner>(`/partners/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deletePartner: (id: number) => request<void>(`/partners/${id}`, { method: "DELETE" }),
  warehouses: () => request<Warehouse[]>("/warehouses"),
  createWarehouse: (payload: Partial<Warehouse>) =>
    request<Warehouse>("/warehouses", { method: "POST", body: JSON.stringify(payload) }),
  updateWarehouse: (id: number, payload: Partial<Warehouse>) =>
    request<Warehouse>(`/warehouses/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteWarehouse: (id: number) => request<void>(`/warehouses/${id}`, { method: "DELETE" }),
  documents: () => request<Document[]>("/documents"),
  document: (id: number) => request<Document>(`/documents/${id}`),
  createDocument: (payload: Partial<Document>) =>
    request<Document>("/documents", { method: "POST", body: JSON.stringify(payload) }),
  updateDocument: (id: number, payload: Partial<Document>) =>
    request<Document>(`/documents/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  addDocumentLine: (documentId: number, payload: { product_id: number; quantity: string; price: string }) =>
    request<DocumentLine>(`/documents/${documentId}/lines`, { method: "POST", body: JSON.stringify(payload) }),
  postDocument: (documentId: number) => request<Document>(`/documents/${documentId}/post`, { method: "POST" }),
  cancelDocument: (documentId: number) => request<Document>(`/documents/${documentId}/cancel`, { method: "POST" }),
  deleteDocument: (documentId: number) => request<void>(`/documents/${documentId}`, { method: "DELETE" }),
  deleteDocumentLine: (documentId: number, lineId: number) => request<void>(`/documents/${documentId}/lines/${lineId}`, { method: "DELETE" }),
  printDocument: (documentId: number) => download(`/documents/${documentId}/print.html`),
  stockBalances: (params = "") => request<StockBalance[]>(`/stock/balances${params}`),
  stockMovements: (params = "") => request<StockMovement[]>(`/stock/movements${params}`),
  payments: () => request<Payment[]>("/payments"),
  createPayment: (payload: Partial<Payment>) =>
    request<Payment>("/payments", { method: "POST", body: JSON.stringify(payload) }),
  postPayment: (paymentId: number) => request<Payment>(`/payments/${paymentId}/post`, { method: "POST" }),
  cancelPayment: (paymentId: number) => request<Payment>(`/payments/${paymentId}/cancel`, { method: "POST" }),
  partnerBalances: () => request<PartnerBalance[]>("/partners/balances"),
  partnerBalance: (partnerId: number) => request<PartnerBalance>(`/partners/${partnerId}/balance`),
  partnerStatement: (partnerId: number) => request<PartnerStatementRow[]>(`/partners/${partnerId}/statement`),
  cashOperations: () => request<CashOperation[]>("/cash/operations"),
  createCashOperation: (payload: Partial<CashOperation>) =>
    request<CashOperation>("/cash/operations", { method: "POST", body: JSON.stringify(payload) }),
  cancelCashOperation: (operationId: number) => request<CashOperation>(`/cash/operations/${operationId}/cancel`, { method: "POST" }),
  cashBalance: () => request<CashBalance>("/cash/balance"),
  cashBook: () => request<CashBookRow[]>("/cash/book"),
  reportStockBalances: (params = "") => request<StockBalancesReport>(`/reports/stock-balances${params}`),
  reportStockMovements: (params = "") => request<StockMovementsReport>(`/reports/stock-movements${params}`),
  reportPartnerDebts: (params = "") => request<PartnerDebtsReport>(`/reports/partner-debts${params}`),
  reportCashBook: (params = "") => request<CashBookReport>(`/reports/cash-book${params}`),
  reportDocumentsRegister: (params = "") => request<DocumentsRegisterReport>(`/reports/documents-register${params}`),
  exportReport: (report: string, params = "") => download(`/reports/${report}/export${params}`),
  importTemplate: (type: string) => download(`/import/templates/${type}.xlsx`),
  importDryRun: (type: string, file: File) =>
    file.arrayBuffer().then((body) => request<ImportSummary>(`/import/${type}/dry-run`, {
      method: "POST",
      body,
      headers: { "Content-Type": "application/octet-stream", "X-Filename": file.name }
    })),
  importApply: (type: string, file: File) =>
    file.arrayBuffer().then((body) => request<ImportSummary>(`/import/${type}/apply`, {
      method: "POST",
      body,
      headers: { "Content-Type": "application/octet-stream", "X-Filename": file.name }
    }))
};
