import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { useAuth } from "../auth";
import { formatCode, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Currency, Document, Partner, Product, Warehouse, api } from "../lib/api";

export function DocumentEditor() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { can } = useAuth();
  const { id } = useParams();
  const documentId = Number(id);
  const [document, setDocument] = useState<Document | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("0");
  const [productSearch, setProductSearch] = useState("");
  const [stockBalance, setStockBalance] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [header, setHeader] = useState({
    document_type: "incoming",
    number: "",
    document_date: "",
    warehouse_id: "",
    destination_warehouse_id: "",
    partner_id: "",
    currency_code: "RUB_PMR",
    exchange_rate: "1",
    note: ""
  });

  const isIncoming = header.document_type === "incoming";
  const lineSum = useMemo(() => Number(quantity || 0) * Number(price || 0), [quantity, price]);
  const baseLineSum = useMemo(() => lineSum * Number(header.exchange_rate || 1), [lineSum, header.exchange_rate]);
  const selectedProduct = useMemo(() => products.find((item) => String(item.id) === productId), [products, productId]);
  const baseUnitCost = useMemo(() => Number(price || 0) * Number(header.exchange_rate || 1), [price, header.exchange_rate]);
  const salePriceReview = useMemo(() => {
    if (!isIncoming || !selectedProduct?.base_price || baseUnitCost <= 0) return null;
    const salePrice = Number(selectedProduct.base_price);
    if (!Number.isFinite(salePrice) || salePrice <= 0) return null;
    if (baseUnitCost === salePrice) return null;
    return {
      direction: baseUnitCost > salePrice ? "higher" : "lower",
      salePrice,
      baseUnitCost
    };
  }, [isIncoming, selectedProduct, baseUnitCost]);
  const filteredProducts = useMemo(() => {
    const search = productSearch.trim().toLowerCase();
    if (!search) return products;
    return products.filter((product) => `${product.name} ${product.sku ?? ""}`.toLowerCase().includes(search));
  }, [products, productSearch]);
  const filteredPartners = useMemo(() => {
    if (header.document_type === "transfer" || header.document_type === "adjustment") {
      return [];
    }
    if (header.document_type === "incoming") {
      return partners.filter((partner) => partner.partner_type === "supplier" || partner.partner_type === "both");
    }
    if (header.document_type === "outgoing") {
      return partners.filter((partner) => partner.partner_type === "customer" || partner.partner_type === "both");
    }
    return partners;
  }, [partners, header.document_type]);

  function isPartnerAllowed(partner: Partner | undefined, documentType: string) {
    if (!partner || documentType === "adjustment" || documentType === "transfer") return true;
    if (documentType === "incoming") return partner.partner_type === "supplier" || partner.partner_type === "both";
    if (documentType === "outgoing") return partner.partner_type === "customer" || partner.partner_type === "both";
    return true;
  }

  function load() {
    if (!documentId) return;
    api.document(documentId).then((doc) => {
      setDocument(doc);
      setHeader({
        document_type: doc.document_type,
        number: doc.number ?? "",
        document_date: doc.document_date,
        warehouse_id: doc.warehouse_id ? String(doc.warehouse_id) : "",
        destination_warehouse_id: doc.destination_warehouse_id ? String(doc.destination_warehouse_id) : "",
        partner_id: doc.partner_id ? String(doc.partner_id) : "",
        currency_code: doc.currency_code ?? "RUB_PMR",
        exchange_rate: doc.exchange_rate ?? "1",
        note: doc.note ?? ""
      });
    }).catch((exc) => setError(String(exc)));
  }

  useEffect(() => {
    load();
    api.products().then(setProducts).catch(() => setProducts([]));
    api.partners().then(setPartners).catch(() => setPartners([]));
    api.warehouses().then(setWarehouses).catch(() => setWarehouses([]));
    api.currencies().then(setCurrencies).catch(() => setCurrencies([]));
  }, [documentId]);

  useEffect(() => {
    if (!productId || !header.warehouse_id || !can("stock.read")) {
      setStockBalance(null);
      return;
    }
    api.stockBalances(`?warehouse_id=${header.warehouse_id}&product_id=${productId}`).then((rows) => {
      setStockBalance(rows[0]?.quantity ?? "0");
    }).catch(() => setStockBalance(null));
  }, [productId, header.warehouse_id]);

  function setSelectedProduct(nextProductId: string) {
    setProductId(nextProductId);
    const product = products.find((item) => String(item.id) === nextProductId);
    if (product?.base_price !== undefined && product.base_price !== null) {
      setPrice(String(product.base_price));
    }
  }

  function setDocumentType(nextType: string) {
    const currentPartner = partners.find((partner) => String(partner.id) === header.partner_id);
    if (nextType === "transfer" || nextType === "adjustment") {
      setHeader({ ...header, document_type: nextType, partner_id: "", destination_warehouse_id: nextType === "transfer" ? header.destination_warehouse_id : "", currency_code: "RUB_PMR", exchange_rate: "1" });
      return;
    }
    if (!isPartnerAllowed(currentPartner, nextType)) {
      setHeader({ ...header, document_type: nextType, partner_id: "", destination_warehouse_id: "", currency_code: nextType === "incoming" ? header.currency_code : "RUB_PMR", exchange_rate: nextType === "incoming" ? header.exchange_rate : "1" });
      setError(t("invalidPartnerForDocument"));
      showToast("warning", t("invalidPartnerForDocument"));
      return;
    }
    setHeader({ ...header, document_type: nextType, destination_warehouse_id: "", currency_code: nextType === "incoming" ? header.currency_code : "RUB_PMR", exchange_rate: nextType === "incoming" ? header.exchange_rate : "1" });
  }

  function setCurrency(nextCurrency: string) {
    setHeader({ ...header, currency_code: nextCurrency, exchange_rate: nextCurrency === "RUB_PMR" ? "1" : header.exchange_rate });
    if (nextCurrency !== "RUB_PMR") {
      api.latestExchangeRate(nextCurrency, header.document_date).then((rate) => {
        setHeader((current) => current.currency_code === nextCurrency ? { ...current, exchange_rate: rate.rate_to_base } : current);
      }).catch(() => {
        showToast("warning", t("exchangeRateRequired"));
      });
    }
  }

  function handleError(exc: unknown) {
    const message = exc instanceof Error ? exc.message : String(exc);
    const friendly = message.includes("Not enough stock") ? t("insufficientStock") : message;
    setError(friendly);
    showToast(message.includes("409") ? "warning" : "error", friendly);
  }

  function addLine() {
    setError("");
    if (Number(quantity) <= 0) {
      setError(t("invalidQuantity"));
      showToast("warning", t("invalidQuantity"));
      return;
    }
    if (Number(price) < 0) {
      setError(t("invalidPrice"));
      showToast("warning", t("invalidPrice"));
      return;
    }
    if (isIncoming && Number(header.exchange_rate) <= 0) {
      setError(t("invalidExchangeRate"));
      showToast("warning", t("invalidExchangeRate"));
      return;
    }
    api
      .addDocumentLine(documentId, { product_id: Number(productId), quantity, price: isIncoming ? "0" : price, foreign_price: isIncoming ? price : null })
      .then(() => {
        showToast("success", t("saved"));
        load();
      })
      .catch(handleError);
  }

  function saveHeader() {
    setError("");
    api
      .updateDocument(documentId, {
        document_type: header.document_type,
        number: header.number || null,
        document_date: header.document_date,
        warehouse_id: header.warehouse_id ? Number(header.warehouse_id) : null,
        destination_warehouse_id: header.destination_warehouse_id ? Number(header.destination_warehouse_id) : null,
        partner_id: header.partner_id ? Number(header.partner_id) : null,
        currency_code: isIncoming ? header.currency_code : "RUB_PMR",
        exchange_rate: isIncoming ? header.exchange_rate : "1",
        note: header.note || null
      })
      .then((doc) => {
        setDocument(doc);
        showToast("success", t("saved"));
        load();
      })
      .catch(handleError);
  }

  function post() {
    setError("");
    if (!window.confirm(t("postConfirm"))) return;
    api.postDocument(documentId).then((doc) => {
      setDocument(doc);
      showToast("success", t("postedSuccess"));
      load();
    }).catch(handleError);
  }

  function cancel() {
    setError("");
    if (!window.confirm(t("cancelConfirm"))) return;
    api.cancelDocument(documentId).then((doc) => {
      setDocument(doc);
      showToast("success", t("cancelledSuccess"));
      load();
    }).catch(handleError);
  }

  function deleteDraft() {
    setError("");
    if (!window.confirm(t("deleteDraftConfirm"))) return;
    api.deleteDocument(documentId).then(() => {
      showToast("success", t("deleteDraft"));
      window.location.href = "/documents";
    }).catch(handleError);
  }

  function deleteLine(lineId: number) {
    setError("");
    if (!window.confirm(t("deleteLineConfirm"))) return;
    api.deleteDocumentLine(documentId, lineId).then(() => {
      showToast("success", t("deleteLine"));
      load();
    }).catch(handleError);
  }

  function print() {
    setError("");
    api.printDocument(documentId)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank", "noopener,noreferrer");
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        showToast("success", t("printOpened"));
      })
      .catch(handleError);
  }

  function downloadPdf() {
    setError("");
    api.printDocumentPdf(documentId)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const link = window.document.createElement("a");
        link.href = url;
        link.download = `document-${documentId}.pdf`;
        link.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        showToast("success", t("pdfDownloaded"));
      })
      .catch(handleError);
  }

  const isDraft = document?.status === "draft";
  const isPosted = document?.status === "posted";
  const isCancelled = document?.status === "cancelled";
  const readOnlyReason = isPosted ? t("documentPostedReadOnly") : isCancelled ? t("documentCancelledReadOnly") : "";

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div className="toolbar">
        <h1 style={{ fontSize: 20, margin: "0 12px 0 0" }}>{t("documentEditorTitle")} #{documentId}</h1>
        <Link className="button" to="/documents">{t("backToDocuments")}</Link>
        <button className="button" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update")} onClick={saveHeader}>{t("save")}</button>
        <button className="button primary" title={!can("documents.post") ? t("noPermission") : ""} disabled={!can("documents.post") || !isDraft} onClick={post}>{t("post")}</button>
        <button className="button" title={!can("documents.cancel") ? t("noPermission") : ""} disabled={!can("documents.cancel") || !isPosted} onClick={cancel}>{t("cancel")}</button>
        <button className="button" title={!can("documents.delete") ? t("noPermission") : ""} disabled={!can("documents.delete") || !isDraft} onClick={deleteDraft}>{t("deleteDraft")}</button>
        <button className="button" title={!can("documents.read") ? t("noPermission") : ""} disabled={!can("documents.read")} onClick={print}>{t("print")}</button>
        <button className="button" title={!can("documents.read") ? t("noPermission") : ""} disabled={!can("documents.read")} onClick={downloadPdf}>{t("downloadPdf")}</button>
      </div>
      {error ? <div className="panel error-panel">{error}</div> : null}
      {readOnlyReason ? <div className="panel" style={{ padding: 10, color: "#52616f", fontSize: 13 }}>{readOnlyReason}</div> : null}
      <div className="panel form-grid">
        <div className="field">
          <label>{t("type")}</label>
          <select
            value={header.document_type}
            onChange={(event) => setDocumentType(event.target.value)}
            disabled={!isDraft}
          >
            <option value="incoming">{t("incoming")}</option>
            <option value="outgoing">{t("outgoing")}</option>
            <option value="adjustment">{t("adjustment")}</option>
            <option value="transfer">{t("transfer")}</option>
          </select>
        </div>
        <div className="field"><label>{t("status")}</label><div style={{ paddingTop: 5 }}><StatusBadge status={document?.status} label={formatCode(document?.status, t)} /></div></div>
        <div className="field"><label>{t("number")}</label><input value={header.number} onChange={(event) => setHeader({ ...header, number: event.target.value })} disabled={!isDraft} /></div>
        <div className="field"><label>{t("date")}</label><input type="date" value={header.document_date} onChange={(event) => setHeader({ ...header, document_date: event.target.value })} disabled={!isDraft} /></div>
        <div className="field">
          <label>{header.document_type === "transfer" ? t("sourceWarehouse") : t("warehouse")}</label>
          <select value={header.warehouse_id} onChange={(event) => setHeader({ ...header, warehouse_id: event.target.value })} disabled={!isDraft}>
            <option value="">{t("notSelected")}</option>
            {warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
          </select>
        </div>
        {header.document_type === "transfer" ? (
          <div className="field">
            <label>{t("destinationWarehouse")}</label>
            <select value={header.destination_warehouse_id} onChange={(event) => setHeader({ ...header, destination_warehouse_id: event.target.value })} disabled={!isDraft}>
              <option value="">{t("notSelected")}</option>
              {warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
            </select>
          </div>
        ) : null}
        <div className="field">
          <label>{t("partner")}</label>
          <select value={header.partner_id} onChange={(event) => setHeader({ ...header, partner_id: event.target.value })} disabled={!isDraft || header.document_type === "transfer" || header.document_type === "adjustment"}>
            <option value="">{t("notSelected")}</option>
            {filteredPartners.map((partner) => <option key={partner.id} value={partner.id}>{partner.name} - {formatCode(partner.partner_type, t)}</option>)}
          </select>
        </div>
        <div className="field"><label>{t("total")}</label><input value={formatMoney(document?.total_amount ?? "0")} readOnly /></div>
        {header.document_type === "incoming" ? (
          <>
            <div className="field">
              <label>{t("currency")}</label>
              <select value={header.currency_code} onChange={(event) => setCurrency(event.target.value)} disabled={!isDraft}>
                {currencies.map((currency) => <option key={currency.code} value={currency.code}>{currency.code} - {currency.name}</option>)}
              </select>
            </div>
            <div className="field"><label>{t("exchangeRate")}</label><input value={header.exchange_rate} onChange={(event) => setHeader({ ...header, exchange_rate: event.target.value })} disabled={!isDraft || header.currency_code === "RUB_PMR"} /></div>
            <div className="field"><label>{t("foreignTotal")}</label><input value={`${formatMoney(document?.foreign_total_amount ?? "0")} ${document?.currency_code ?? header.currency_code}`} readOnly /></div>
          </>
        ) : null}
        <div className="field"><label>{t("note")}</label><input value={header.note} onChange={(event) => setHeader({ ...header, note: event.target.value })} disabled={!isDraft} /></div>
        <div className="field"><label>{t("warehouse")}</label><input value={document?.warehouse_name ?? ""} readOnly /></div>
        <div className="field"><label>{t("destinationWarehouse")}</label><input value={document?.destination_warehouse_name ?? ""} readOnly /></div>
        <div className="field"><label>{t("partner")}</label><input value={document?.partner_name ?? ""} readOnly /></div>
      </div>

      <div className="panel form-grid">
        <div className="field">
          <label>{t("productSearch")}</label>
          <input value={productSearch} onChange={(event) => setProductSearch(event.target.value)} disabled={!isDraft} />
        </div>
        <div className="field">
          <label>{t("product")}</label>
          <select value={productId} onChange={(event) => setSelectedProduct(event.target.value)} disabled={!isDraft}>
            <option value="">{t("selectProduct")}</option>
            {filteredProducts.map((product) => <option key={product.id} value={product.id}>{product.name}{product.sku ? ` (${product.sku})` : ""}</option>)}
          </select>
        </div>
        <div className="field"><label>{t("quantity")}</label><input value={quantity} onChange={(event) => setQuantity(event.target.value)} disabled={!isDraft} /></div>
        <div className="field"><label>{isIncoming ? t("foreignPrice") : t("price")}</label><input value={price} onChange={(event) => setPrice(event.target.value)} disabled={!isDraft} /></div>
        <div className="field"><label>{isIncoming ? t("foreignSum") : t("sum")}</label><input value={lineSum.toFixed(2)} readOnly /></div>
        {isIncoming ? <div className="field"><label>{t("baseSum")}</label><input value={baseLineSum.toFixed(2)} readOnly /></div> : null}
        <div className="field"><label>{t("stockBalance")}</label><input value={stockBalance ?? ""} readOnly /></div>
        <div className="field"><label>&nbsp;</label><button className="button primary" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isDraft} onClick={addLine}>{t("addLine")}</button></div>
      </div>
      {salePriceReview ? (
        <div className="panel" style={{ padding: 10, color: "#7a4b00", background: "#fff7e6", borderColor: "#f0c36d", fontSize: 13 }}>
          {t("salePriceReviewHint")} {t(salePriceReview.direction === "higher" ? "purchasePriceHigher" : "purchasePriceLower")} {t("currentSalePrice")}: {formatMoney(salePriceReview.salePrice.toFixed(2))}; {t("newBasePurchasePrice")}: {formatMoney(salePriceReview.baseUnitCost.toFixed(2))}.
        </div>
      ) : null}

      <DataTable
        rows={document?.lines ?? []}
        emptyMessage={t("noLines")}
        searchable
        columns={[
          { key: "product_name", header: t("product"), sortable: true },
          { key: "quantity", header: t("quantity"), sortable: true },
          ...(document?.document_type === "incoming" ? [{ key: "foreign_price", header: t("foreignPrice"), sortable: true, render: (row: any) => row.foreign_price ? `${formatMoney(row.foreign_price)} ${document.currency_code}` : "" }] : []),
          { key: "price", header: t("price"), sortable: true, render: (row) => formatMoney(row.price) },
          ...(document?.document_type === "incoming" ? [{ key: "foreign_line_total", header: t("foreignSum"), sortable: true, render: (row: any) => row.foreign_line_total ? `${formatMoney(row.foreign_line_total)} ${document.currency_code}` : "" }] : []),
          { key: "line_total", header: t("sum"), sortable: true, render: (row) => formatMoney(row.line_total) },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => <button className="button" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isDraft} onClick={() => deleteLine(row.id)}>{t("deleteLine")}</button>
          }
        ]}
      />
      <p style={{ color: "#52616f", fontSize: 13 }}>
        TODO LEGACY_RULE_REQUIRED: final posting, cancellation, accounting, pricing, VAT, and debt rules.
      </p>
    </div>
  );
}
