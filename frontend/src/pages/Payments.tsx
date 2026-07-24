import { useEffect, useMemo, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatCode, formatDate, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { Document, Partner, PartnerBalance, Payment, api } from "../lib/api";

export function Payments() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<Payment[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [balances, setBalances] = useState<PartnerBalance[]>([]);
  const [partnerId, setPartnerId] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [paymentType, setPaymentType] = useState("customer_payment");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);

  const partnerOptions = useMemo(() => partners.filter((partner) => {
    if (!partner.is_active) return false;
    if (paymentType === "customer_payment") return partner.partner_type === "customer" || partner.partner_type === "both";
    if (paymentType === "supplier_payment") return partner.partner_type === "supplier" || partner.partner_type === "both";
    return true;
  }), [partners, paymentType]);
  const matchingDocuments = useMemo(() => documents.filter((document) => {
    if (!partnerId || document.status !== "posted" || String(document.partner_id) !== partnerId) return false;
    if (paymentType === "customer_payment") return document.document_type === "outgoing";
    if (paymentType === "supplier_payment") return document.document_type === "incoming";
    return true;
  }), [documents, partnerId, paymentType]);
  const selectedBalance = useMemo(
    () => balances.find((balance) => String(balance.partner_id) === partnerId),
    [balances, partnerId]
  );

  useEffect(() => {
    if (!partnerId) {
      setDocuments([]);
      return;
    }
    const documentType = paymentType === "customer_payment"
      ? "outgoing"
      : paymentType === "supplier_payment"
        ? "incoming"
        : "";
    const params = new URLSearchParams({
      partner_id: partnerId,
      status: "posted",
      limit: "500"
    });
    if (documentType) params.set("document_type", documentType);
    api.documents(`?${params.toString()}`)
      .then(setDocuments)
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadDocumentsError")));
  }, [partnerId, paymentType]);

  function setPaymentTypeChecked(nextType: string) {
    const currentPartner = partners.find((partner) => String(partner.id) === partnerId);
    const allowed =
      !currentPartner ||
      nextType === "refund" ||
      (nextType === "customer_payment" && ["customer", "both"].includes(currentPartner.partner_type)) ||
      (nextType === "supplier_payment" && ["supplier", "both"].includes(currentPartner.partner_type));
    setPaymentType(nextType);
    setDocumentId("");
    if (!allowed) {
      setPartnerId("");
      setError(t("invalidPartnerForPayment"));
    }
  }

  function load() {
    Promise.all([api.payments(), api.partners(), api.partnerBalances()])
      .then(([paymentRows, partnerRows, balanceRows]) => {
        setRows(paymentRows);
        setPartners(partnerRows);
        setBalances(balanceRows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiLoadPaymentsError")));
  }

  function resetForm() {
    setEditingId(null);
    setPartnerId("");
    setDocumentId("");
    setPaymentDate(new Date().toISOString().slice(0, 10));
    setPaymentType("customer_payment");
    setAmount("");
    setMethod("cash");
    setError("");
  }

  function edit(row: Payment) {
    if (row.status !== "draft") return;
    setEditingId(row.id);
    setPartnerId(String(row.partner_id));
    setDocumentId(row.document_id ? String(row.document_id) : "");
    setPaymentDate(row.payment_date.slice(0, 10));
    setPaymentType(row.payment_type);
    setAmount(row.amount);
    setMethod(row.method ?? "cash");
    setError("");
  }

  function create() {
    if (!partnerId || !amount) return;
    const payload = {
      partner_id: Number(partnerId),
      document_id: documentId ? Number(documentId) : null,
      payment_date: paymentDate,
      payment_type: paymentType,
      status: "draft",
      amount,
      method
    };
    const request = editingId ? api.updatePayment(editingId, payload) : api.createPayment(payload);
    request
      .then(() => {
        resetForm();
        load();
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("apiCreatePaymentError")));
  }

  function post(id: number) {
    api.postPayment(id).then(load).catch((err) => setError(err instanceof Error ? err.message : t("apiPostPaymentError")));
  }

  function cancel(id: number) {
    api.cancelPayment(id).then(load).catch((err) => setError(err instanceof Error ? err.message : t("apiCancelPaymentError")));
  }

  function removeDraft(id: number) {
    if (!window.confirm(t("deleteDraftConfirm"))) return;
    api.deletePayment(id).then(() => {
      if (editingId === id) resetForm();
      load();
    }).catch((err) => setError(err instanceof Error ? err.message : t("deleteError")));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <PageScaffold title={t("payments")}>
      <div className="panel form-grid" style={{ marginBottom: 10 }}>
        <div className="field"><label>{t("date")}</label><input type="date" value={paymentDate} onChange={(event) => setPaymentDate(event.target.value)} /></div>
        <div className="field">
          <label>{t("partner")}</label>
          <select
            data-testid="payment-partner"
            value={partnerId}
            onChange={(event) => {
              setPartnerId(event.target.value);
              setDocumentId("");
            }}
          >
            <option value="">{t("selectPartner")}</option>
            {partnerOptions.map((partner) => <option key={partner.id} value={partner.id}>{partner.name} - {formatCode(partner.partner_type, t)}</option>)}
          </select>
        </div>
        <div className="field">
          <label>{t("type")}</label>
          <select data-testid="payment-type" value={paymentType} onChange={(event) => setPaymentTypeChecked(event.target.value)}>
            <option value="customer_payment">{t("customerPayment")}</option>
            <option value="supplier_payment">{t("supplierPayment")}</option>
            <option value="refund">{t("refund")}</option>
          </select>
        </div>
        <div className="field">
          <label>{t("relatedDocument")}</label>
          <select data-testid="payment-document" value={documentId} onChange={(event) => setDocumentId(event.target.value)} disabled={!partnerId}>
            <option value="">{t("paymentOnAccount")}</option>
            {matchingDocuments.map((document) => (
              <option key={document.id} value={document.id}>
                {formatCode(document.document_type, t)} # {document.number || document.id} - {formatMoney(document.total_amount)}
              </option>
            ))}
          </select>
          {partnerId && matchingDocuments.length === 0 ? <small>{t("noMatchingDocuments")}</small> : null}
        </div>
        <div className="field">
          <label>{t("amount")}</label>
          <input data-testid="payment-amount" type="number" min="0.01" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} />
          {selectedBalance ? <small>{t("currentPartnerBalance")}: {formatMoney(selectedBalance.balance)}</small> : null}
        </div>
        <div className="field">
          <label>{t("method")}</label>
          <select value={method} onChange={(event) => setMethod(event.target.value)}>
            <option value="cash">{t("cash")}</option>
            <option value="bank">{t("bank")}</option>
          </select>
        </div>
        <div className="field">
          <label>&nbsp;</label>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="button primary"
              title={!can(editingId ? "payments.update" : "payments.create") ? t("noPermission") : ""}
              disabled={!can(editingId ? "payments.update" : "payments.create")}
              data-testid="payment-save"
              onClick={create}
            >
              {editingId ? t("save") : t("createPayment")}
            </button>
            {editingId ? <button className="button" onClick={resetForm}>{t("cancel")}</button> : null}
          </div>
        </div>
      </div>
      {error ? <p style={{ color: "#b42318", fontSize: 13 }}>{error}</p> : null}
      <DataTable<Payment>
        rows={rows}
        emptyMessage={t("noPayments")}
        searchable
        columns={[
          { key: "payment_date", header: t("date"), sortable: true, render: (row) => formatDate(row.payment_date) },
          { key: "partner_name", header: t("partner"), sortable: true },
          { key: "document_number", header: t("document"), sortable: true },
          { key: "payment_type", header: t("type"), sortable: true, render: (row) => formatCode(row.payment_type, t) },
          { key: "amount", header: t("amount"), sortable: true, render: (row) => formatMoney(row.amount) },
          { key: "method", header: t("method"), sortable: true, render: (row) => formatCode(row.method, t) },
          { key: "status", header: t("status"), sortable: true, render: (row) => <StatusBadge status={row.status} label={formatCode(row.status, t)} /> },
          {
            key: "cash_operation_status",
            header: t("cash"),
            render: (row) => row.cash_operation_id ? `#${row.cash_operation_id} ${formatCode(row.cash_operation_status, t)}` : ""
          },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                <button className="button" title={!can("payments.update") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.update")} onClick={() => edit(row)}>{t("edit")}</button>
                <button data-testid={`payment-post-${row.id}`} className="button" title={!can("payments.post") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.post")} onClick={() => post(row.id)}>{t("post")}</button>
                <button className="button" title={!can("payments.cancel") ? t("noPermission") : ""} disabled={row.status !== "posted" || !can("payments.cancel")} onClick={() => cancel(row.id)}>{t("cancel")}</button>
                <button className="button" title={!can("payments.delete") ? t("noPermission") : ""} disabled={row.status !== "draft" || !can("payments.delete")} onClick={() => removeDraft(row.id)}>{t("deleteDraft")}</button>
              </div>
            )
          }
        ]}
      />
    </PageScaffold>
  );
}
