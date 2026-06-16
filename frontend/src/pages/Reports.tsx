import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { useAuth } from "../auth";
import { formatCode } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import {
  CashBookReport,
  DocumentsRegisterReport,
  PartnerDebtsReport,
  StockBalancesReport,
  StockMovementsReport,
  api
} from "../lib/api";

type Tab = "stock-balances" | "stock-movements" | "partner-debts" | "cash-book" | "documents-register";

const emptyStockBalances: StockBalancesReport = { rows: [], total_quantity: "0" };
const emptyStockMovements: StockMovementsReport = { rows: [], total_quantity: "0" };
const emptyPartnerDebts: PartnerDebtsReport = { rows: [], total_partner_debt: "0" };
const emptyCashBook: CashBookReport = { rows: [], cash_in_total: "0", cash_out_total: "0", cash_balance: "0" };
const emptyDocumentsRegister: DocumentsRegisterReport = { rows: [], total_amount: "0" };

function params(values: Record<string, string | boolean | undefined>) {
  const search = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== "" && value !== false) {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function Reports() {
  const { t } = useI18n();
  const { can } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("stock-balances");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  const [warehouseId, setWarehouseId] = useState("");
  const [productId, setProductId] = useState("");
  const [partnerId, setPartnerId] = useState("");
  const [partnerType, setPartnerType] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [operationType, setOperationType] = useState("");
  const [status, setStatus] = useState("");
  const [onlyWithBalance, setOnlyWithBalance] = useState(false);

  const [stockBalances, setStockBalances] = useState(emptyStockBalances);
  const [stockMovements, setStockMovements] = useState(emptyStockMovements);
  const [partnerDebts, setPartnerDebts] = useState(emptyPartnerDebts);
  const [cashBook, setCashBook] = useState(emptyCashBook);
  const [documentsRegister, setDocumentsRegister] = useState(emptyDocumentsRegister);

  function currentParams(extra: Record<string, string | boolean | undefined> = {}) {
    const values =
      tab === "stock-balances"
        ? { warehouse_id: warehouseId, product_id: productId, search }
        : tab === "stock-movements"
          ? { date_from: dateFrom, date_to: dateTo, warehouse_id: warehouseId, product_id: productId, document_id: documentId }
          : tab === "partner-debts"
            ? { partner_id: partnerId, partner_type: partnerType, only_with_balance: onlyWithBalance }
            : tab === "cash-book"
              ? { date_from: dateFrom, date_to: dateTo, operation_type: operationType, status }
              : { date_from: dateFrom, date_to: dateTo, document_type: documentType, status, partner_id: partnerId, warehouse_id: warehouseId };
    return params({ ...values, ...extra });
  }

  function load() {
    if (!can("reports.read")) {
      return;
    }
    setLoading(true);
    setError("");
    const request =
      tab === "stock-balances"
        ? api.reportStockBalances(currentParams()).then(setStockBalances)
        : tab === "stock-movements"
          ? api.reportStockMovements(currentParams()).then(setStockMovements)
          : tab === "partner-debts"
            ? api.reportPartnerDebts(currentParams()).then(setPartnerDebts)
            : tab === "cash-book"
              ? api.reportCashBook(currentParams()).then(setCashBook)
              : api.reportDocumentsRegister(currentParams()).then(setDocumentsRegister);

    request.catch((exc) => {
      setError(exc instanceof Error ? exc.message : t("apiLoadReportsError"));
    }).finally(() => setLoading(false));
  }

  function exportCurrent(format: "xlsx" | "csv") {
    setExporting(true);
    setError("");
    api.exportReport(tab, currentParams({ format }))
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${tab}.${format}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showToast("success", t("exportSuccess"));
      })
      .catch((exc) => {
        const message = exc instanceof Error ? exc.message : t("exportError");
        setError(message);
        showToast("error", message);
      })
      .finally(() => setExporting(false));
  }

  useEffect(() => {
    load();
  }, [tab]);

  if (!can("reports.read")) {
    return (
      <div className="panel error-panel">
        {t("noAccess")}
      </div>
    );
  }

  return (
    <>
      <div className="toolbar">
        <h1 style={{ fontSize: 20, margin: "0 12px 0 0" }}>{t("reports")}</h1>
        <button className="button" disabled={exporting} onClick={() => exportCurrent("xlsx")}>{t("exportXlsx")}</button>
        <button className="button" disabled={exporting} onClick={() => exportCurrent("csv")}>{t("exportCsv")}</button>
      </div>

      <div className="toolbar">
        <button className={`button ${tab === "stock-balances" ? "primary" : ""}`} onClick={() => setTab("stock-balances")}>{t("stockBalancesReport")}</button>
        <button className={`button ${tab === "stock-movements" ? "primary" : ""}`} onClick={() => setTab("stock-movements")}>{t("stockMovementsReport")}</button>
        <button className={`button ${tab === "partner-debts" ? "primary" : ""}`} onClick={() => setTab("partner-debts")}>{t("partnerDebts")}</button>
        <button className={`button ${tab === "cash-book" ? "primary" : ""}`} onClick={() => setTab("cash-book")}>{t("cashBook")}</button>
        <button className={`button ${tab === "documents-register" ? "primary" : ""}`} onClick={() => setTab("documents-register")}>{t("documentsRegister")}</button>
      </div>

      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        {["stock-balances", "stock-movements", "documents-register"].includes(tab) ? (
          <>
            <div className="field"><label>{t("warehouse")} ID</label><input value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} /></div>
            <div className="field"><label>{t("product")} ID</label><input value={productId} onChange={(event) => setProductId(event.target.value)} disabled={tab === "documents-register"} /></div>
          </>
        ) : null}
        {tab === "stock-balances" ? (
          <div className="field"><label>{t("search")}</label><input value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        ) : null}
        {["stock-movements", "cash-book", "documents-register"].includes(tab) ? (
          <>
            <div className="field"><label>{t("dateFrom")}</label><input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></div>
            <div className="field"><label>{t("dateTo")}</label><input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} /></div>
          </>
        ) : null}
        {tab === "stock-movements" ? (
          <div className="field"><label>{t("document")} ID</label><input value={documentId} onChange={(event) => setDocumentId(event.target.value)} /></div>
        ) : null}
        {["partner-debts", "documents-register"].includes(tab) ? (
          <div className="field"><label>{t("partner")} ID</label><input value={partnerId} onChange={(event) => setPartnerId(event.target.value)} /></div>
        ) : null}
        {tab === "partner-debts" ? (
          <>
            <div className="field">
              <label>{t("partnerType")}</label>
              <select value={partnerType} onChange={(event) => setPartnerType(event.target.value)}>
                <option value="">{t("all")}</option>
                <option value="customer">{t("customer")}</option>
                <option value="supplier">{t("supplier")}</option>
                <option value="both">{t("both")}</option>
              </select>
            </div>
            <div className="field"><label>{t("onlyWithBalance")}</label><input type="checkbox" checked={onlyWithBalance} onChange={(event) => setOnlyWithBalance(event.target.checked)} /></div>
          </>
        ) : null}
        {tab === "cash-book" ? (
          <div className="field">
            <label>{t("operationType")}</label>
            <select value={operationType} onChange={(event) => setOperationType(event.target.value)}>
              <option value="">{t("all")}</option>
              <option value="cash_in">{t("cashIn")}</option>
              <option value="cash_out">{t("cashOut")}</option>
              <option value="correction">{t("correction")}</option>
            </select>
          </div>
        ) : null}
        {["cash-book", "documents-register"].includes(tab) ? (
          <div className="field">
            <label>{t("status")}</label>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">{t("all")}</option>
              <option value="draft">{t("draft")}</option>
              <option value="posted">{t("posted")}</option>
              <option value="cancelled">{t("cancelled")}</option>
            </select>
          </div>
        ) : null}
        {tab === "documents-register" ? (
          <div className="field">
            <label>{t("type")}</label>
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              <option value="">{t("all")}</option>
              <option value="incoming">{t("incoming")}</option>
              <option value="outgoing">{t("outgoing")}</option>
              <option value="adjustment">{t("adjustment")}</option>
              <option value="transfer">{t("transfer")}</option>
            </select>
          </div>
        ) : null}
        <div className="field"><label>&nbsp;</label><button className="button primary" onClick={load}>{t("filter")}</button></div>
      </div>

      {loading ? <div className="panel">{t("loading")}</div> : null}
      {exporting ? <div className="panel">{t("export")}</div> : null}
      {error ? <div className="panel error-panel">{error}</div> : null}

      {tab === "stock-balances" ? (
        <>
          <div className="panel summary-row">{t("totalQuantity")}: {stockBalances.total_quantity}</div>
          <DataTable rows={stockBalances.rows} emptyMessage={t("noReportRows")} columns={[
            { key: "warehouse_name", header: t("warehouse") },
            { key: "product_name", header: t("product") },
            { key: "quantity", header: t("quantity") }
          ]} />
        </>
      ) : null}

      {tab === "stock-movements" ? (
        <>
          <div className="panel summary-row">{t("totalQuantity")}: {stockMovements.total_quantity}</div>
          <DataTable rows={stockMovements.rows} emptyMessage={t("noReportRows")} columns={[
            { key: "created_at", header: t("date") },
            { key: "product_name", header: t("product") },
            { key: "warehouse_name", header: t("warehouse") },
            { key: "document_number", header: t("document") },
            { key: "movement_type", header: t("movement"), render: (row) => formatCode(row.movement_type, t) },
            { key: "quantity_delta", header: t("quantity") }
          ]} />
        </>
      ) : null}

      {tab === "partner-debts" ? (
        <>
          <div className="panel summary-row">{t("totalPartnerDebt")}: {partnerDebts.total_partner_debt}</div>
          <DataTable rows={partnerDebts.rows} emptyMessage={t("noReportRows")} columns={[
            { key: "partner_name", header: t("partner") },
            { key: "partner_type", header: t("partnerType"), render: (row) => formatCode(row.partner_type, t) },
            { key: "balance", header: t("balance") }
          ]} />
        </>
      ) : null}

      {tab === "cash-book" ? (
        <>
          <div className="panel summary-row">
            {t("cashInTotal")}: {cashBook.cash_in_total} | {t("cashOutTotal")}: {cashBook.cash_out_total} | {t("cashBalance")}: {cashBook.cash_balance}
          </div>
          <DataTable rows={cashBook.rows} emptyMessage={t("noReportRows")} columns={[
            { key: "operation_date", header: t("date") },
            { key: "operation_type", header: t("type"), render: (row) => formatCode(row.operation_type, t) },
            { key: "status", header: t("status"), render: (row) => formatCode(row.status, t) },
            { key: "partner_name", header: t("partner") },
            { key: "payment_id", header: t("payment") },
            { key: "amount", header: t("amount") },
            { key: "cash_balance", header: t("cashBalance") }
          ]} />
        </>
      ) : null}

      {tab === "documents-register" ? (
        <>
          <div className="panel summary-row">{t("total")}: {documentsRegister.total_amount}</div>
          <DataTable rows={documentsRegister.rows} emptyMessage={t("noReportRows")} columns={[
            { key: "document_date", header: t("date") },
            { key: "document_number", header: t("number") },
            { key: "document_type", header: t("type"), render: (row) => formatCode(row.document_type, t) },
            { key: "status", header: t("status"), render: (row) => formatCode(row.status, t) },
            { key: "partner_name", header: t("partner") },
            { key: "warehouse_name", header: t("warehouse") },
            { key: "destination_warehouse_name", header: t("destinationWarehouse") },
            { key: "total_amount", header: t("sum") }
          ]} />
        </>
      ) : null}
    </>
  );
}
