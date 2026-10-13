import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { CashBookRow, api } from "../lib/api";

const PAGE_SIZE = 25;

export function Cash() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<CashBookRow[]>([]);
  const [balance, setBalance] = useState("0");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageOpeningBalance, setPageOpeningBalance] = useState("0");
  const [pageClosingBalance, setPageClosingBalance] = useState("0");
  const [searchParams] = useSearchParams();
  const [operationDate, setOperationDate] = useState(new Date().toISOString().slice(0, 10));
  const [operationType, setOperationType] = useState(() => {
    const requestedType = searchParams.get("create");
    return requestedType === "cash_out" || requestedType === "correction" ? requestedType : "cash_in";
  });
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  function load() {
    api.cashBookPage(page * PAGE_SIZE, PAGE_SIZE)
      .then((book) => {
        setBalance(book.current_balance);
        setRows(book.items);
        setTotal(book.total);
        setPageOpeningBalance(book.page_opening_balance);
        setPageClosingBalance(book.page_closing_balance);
        setError("");
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadCashError")));
  }

  function create() {
    if (!amount) return;
    if (operationType === "correction" && !note.trim()) {
      setError(t("cashCorrectionNoteRequired"));
      return;
    }
    api
      .createCashOperation({
        operation_date: operationDate,
        operation_type: operationType,
        amount,
        note: note || null
      })
      .then(() => {
        setAmount("");
        setNote("");
        setError("");
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCreateCashError")));
  }

  function cancel(id: number) {
    api
      .cancelCashOperation(id)
      .then(() => {
        setError("");
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCancelCashError")));
  }

  useEffect(() => {
    load();
  }, [page]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <PageScaffold title={t("cash")}>
      <div className="panel" style={{ padding: 12, marginBottom: 10 }}>
        <div style={{ color: "#52616f", fontSize: 12 }}>{t("cashBalance")}</div>
        <div style={{ fontSize: 24, fontWeight: 700 }}>{balance}</div>
      </div>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label>{t("date")}</label><input type="date" value={operationDate} onChange={(event) => setOperationDate(event.target.value)} /></div>
        <div className="field">
          <label>{t("type")}</label>
          <select value={operationType} onChange={(event) => setOperationType(event.target.value)}>
            <option value="cash_in">{t("cashIn")}</option>
            <option value="cash_out">{t("cashOut")}</option>
            <option value="correction">{t("correction")}</option>
          </select>
        </div>
        <div className="field">
          <label>{operationType === "correction" ? t("actualCashBalance") : t("amount")}</label>
          <input
            type="number"
            min={operationType === "correction" ? "0" : "0.01"}
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </div>
        <div className="field"><label>{t("note")}</label><input value={note} onChange={(event) => setNote(event.target.value)} /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can("cash.create") ? t("noPermission") : ""} disabled={!can("cash.create")} onClick={create}>{t("createOperation")}</button></div>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      <DataTable<CashBookRow>
        rows={rows}
        emptyMessage={t("noCash")}
        pageSize={PAGE_SIZE}
        columns={[
          { key: "operation_date", header: t("date"), render: (row) => formatDate(row.operation_date) },
          { key: "operation_type", header: t("type"), render: (row) => formatCode(row.operation_type, t) },
          { key: "amount", header: t("amount"), render: (row) => formatMoney(row.amount) },
          { key: "target_balance", header: t("targetCashBalance"), render: (row) => row.target_balance == null ? "-" : formatMoney(row.target_balance) },
          { key: "partner_name", header: t("partner") },
          { key: "payment_id", header: t("payment") },
          { key: "status", header: t("status"), render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          { key: "balance", header: t("balance"), render: (row) => formatMoney(row.balance) },
          { key: "note", header: t("note") },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <button className="button" title={!can("cash.cancel") ? t("noPermission") : ""} disabled={row.status !== "posted" || !can("cash.cancel")} onClick={() => cancel(row.id)}>{t("cancel")}</button>
            )
          }
        ]}
      />
      {rows.length ? (
        <div className="panel table-footer">
          <span>{t("balance")}: {formatMoney(pageOpeningBalance)} → {formatMoney(pageClosingBalance)} · {t("total")}: {total}</span>
          <span>
            <button className="button" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>‹</button>
            <span style={{ padding: "0 8px" }}>{page + 1} / {pageCount}</span>
            <button className="button" disabled={page >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>›</button>
          </span>
        </div>
      ) : null}
    </PageScaffold>
  );
}
