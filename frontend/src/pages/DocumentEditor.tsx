import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { useConfirmDialog } from "../components/ConfirmDialog";
import { CopyDocumentButton } from "../components/CopyDocumentButton";
import { DocumentRelations } from "../components/DocumentRelations";
import { DraftRecoveryNotice } from "../components/DraftRecoveryNotice";
import { useLocalDraft } from "../hooks/useLocalDraft";
import { useAuth } from "../auth";
import { formatCode, formatMoney, StatusBadge } from "../format";
import { useI18n } from "../i18n";
import { useToast } from "../toast";
import { Currency, Document, DocumentLine, DocumentRevision, Partner, Product, Warehouse, api } from "../lib/api";

export function DocumentEditor() {
  const { t } = useI18n();
  const { showToast } = useToast();
  const { ask, dialog } = useConfirmDialog();
  const { can } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const documentId = Number(id);
  const [document, setDocument] = useState<Document | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [revisions, setRevisions] = useState<DocumentRevision[]>([]);
  const [correctionMode, setCorrectionMode] = useState(false);
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionLines, setCorrectionLines] = useState<DocumentLine[]>([]);
  const [editingCorrectionLineId, setEditingCorrectionLineId] = useState<number | null>(null);
  const [editingDraftLineId, setEditingDraftLineId] = useState<number | null>(null);
  const [savingLine, setSavingLine] = useState(false);
  const productInputRef = useRef<HTMLInputElement>(null);
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [price, setPrice] = useState("0");
  const [productSearch, setProductSearch] = useState("");
  const [productOptionsOpen, setProductOptionsOpen] = useState(false);
  const [productOptionsLoading, setProductOptionsLoading] = useState(true);
  const [activeProductIndex, setActiveProductIndex] = useState(-1);
  const [partnerSearch, setPartnerSearch] = useState("");
  const [stockBalance, setStockBalance] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const allowExitRef = useRef(false);
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
  const [savedHeader, setSavedHeader] = useState<typeof header | null>(null);
  const lineDraftDirty = productId !== "" || productSearch.trim() !== "" || quantity !== "1" || price !== "0";
  const hasUnsavedChanges = document !== null && ((savedHeader !== null && JSON.stringify(header) !== JSON.stringify(savedHeader)) || correctionMode || (document.status === "draft" && lineDraftDirty));
  const blocker = useBlocker(() => hasUnsavedChanges && !allowExitRef.current);

  type InputDraft = {
    header: typeof header;
    productId: string;
    productSearch: string;
    quantity: string;
    price: string;
    editingDraftLineId: number | null;
    editingCorrectionLineId: number | null;
    correctionMode: boolean;
    correctionReason: string;
    correctionLines: DocumentLine[];
  };

  function validInput(value: unknown): value is InputDraft {
    if (!value || typeof value !== "object") return false;
    const saved = value as InputDraft;
    if (!saved.header || Object.keys(header).some((key) => typeof saved.header[key as keyof typeof header] !== "string")
      || ![saved.productId, saved.productSearch, saved.quantity, saved.price, saved.correctionReason].every((item) => typeof item === "string")
      || typeof saved.correctionMode !== "boolean" || !Array.isArray(saved.correctionLines)) return false;
    if (![saved.editingDraftLineId, saved.editingCorrectionLineId].every((item) => item === null || Number.isSafeInteger(item))) return false;
    if (saved.editingDraftLineId !== null && !document?.lines?.some((line) => line.id === saved.editingDraftLineId)) return false;
    if (saved.correctionMode && (document?.status !== "posted" || !can("documents.post"))) return false;
    if (saved.correctionLines.some((line) => !line || !Number.isSafeInteger(line.id) || !Number.isSafeInteger(line.product_id) || line.document_id !== documentId
      || typeof line.quantity !== "string" || typeof line.price !== "string" || typeof line.line_total !== "string")) return false;
    return saved.editingCorrectionLineId === null || saved.correctionLines.some((line) => line.id === saved.editingCorrectionLineId);
  }

  const draft = useLocalDraft<InputDraft>({
    scope: "document",
    entityId: documentId,
    revision: JSON.stringify(document ? [document.id, document.status, document.posting_version, document.updated_at, savedHeader, document.lines] : []),
    value: { header, productId, productSearch, quantity, price, editingDraftLineId, editingCorrectionLineId, correctionMode, correctionReason, correctionLines },
    dirty: hasUnsavedChanges,
    enabled: document?.id === documentId && savedHeader !== null && can("documents.update") && (document.status === "draft" || (document.status === "posted" && can("documents.post"))),
    validate: validInput,
    onRestore: (saved) => {
      setHeader(saved.header);
      setProductId(saved.productId);
      setProductSearch(saved.productSearch);
      setQuantity(saved.quantity);
      setPrice(saved.price);
      setEditingDraftLineId(saved.editingDraftLineId);
      setEditingCorrectionLineId(saved.editingCorrectionLineId);
      setCorrectionMode(saved.correctionMode);
      setCorrectionReason(saved.correctionReason);
      setCorrectionLines(saved.correctionLines);
      if (saved.productId) api.product(Number(saved.productId)).then((product) => {
        if (product.id === Number(saved.productId)) setProducts((current) => current.some((item) => item.id === product.id) ? current : [product, ...current]);
      }).catch(() => undefined);
      if (saved.header.partner_id) api.partner(Number(saved.header.partner_id)).then((partner) => {
        if (partner.id === Number(saved.header.partner_id)) setPartners((current) => current.some((item) => item.id === partner.id) ? current : [partner, ...current]);
      }).catch(() => undefined);
    },
    onDiscard: () => {
      if (document) applyDocument(document);
      setCorrectionMode(false);
      setCorrectionLines([]);
      setCorrectionReason("");
      resetLineEntry();
    },
  });

  useLayoutEffect(() => {
    allowExitRef.current = false;
    setDocument(null);
    setSavedHeader(null);
    setCorrectionMode(false);
    setCorrectionLines([]);
    setCorrectionReason("");
    resetLineEntry();
  }, [documentId]);

  useEffect(() => { setValidationErrors({}); }, [header]);
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm(t(draft.storageError ? "unsavedChangesConfirm" : "leaveRecoverableDocumentConfirm"))) blocker.proceed();
    else blocker.reset();
  }, [blocker.state]);
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const warn = (event: BeforeUnloadEvent) => {
      if (allowExitRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasUnsavedChanges]);

  const isIncoming = header.document_type === "incoming";
  const lineSum = useMemo(() => Number(quantity || 0) * Number(price || 0), [quantity, price]);
  const baseLineSum = useMemo(() => lineSum * Number(header.exchange_rate || 1), [lineSum, header.exchange_rate]);
  const selectedProduct = useMemo(() => products.find((item) => String(item.id) === productId), [products, productId]);
  const baseUnitCost = useMemo(() => Number(price || 0) * Number(header.exchange_rate || 1), [price, header.exchange_rate]);
  const salePriceReview = useMemo(() => {
    if (!isIncoming || !selectedProduct || baseUnitCost <= 0) return null;
    const salePrice = selectedProduct.base_price === null || selectedProduct.base_price === undefined
      ? null
      : Number(selectedProduct.base_price);
    const previousPurchaseCost = selectedProduct.current_cost === null || selectedProduct.current_cost === undefined
      ? null
      : Number(selectedProduct.current_cost);
    const markupPercent = salePrice === null || !Number.isFinite(salePrice)
      ? null
      : ((salePrice - baseUnitCost) / baseUnitCost) * 100;
    const priceReviewRequired = markupPercent === null || markupPercent < 10;
    const costChanged = previousPurchaseCost === null || Math.abs(previousPurchaseCost - baseUnitCost) >= 0.005;
    if (!costChanged && !priceReviewRequired) return null;
    return {
      direction: previousPurchaseCost === null ? "first" : baseUnitCost > previousPurchaseCost ? "higher" : "lower",
      salePrice,
      baseUnitCost,
      previousPurchaseCost,
      markupPercent,
      minimumSalePrice: baseUnitCost * 1.1,
      priceReviewRequired,
      costChanged
    };
  }, [isIncoming, selectedProduct, baseUnitCost]);
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

  function applyDocument(doc: Document) {
    setDocument((current) => current?.id === doc.id && !doc.lines ? { ...current, ...doc } : doc);
    const nextHeader = {
      document_type: doc.document_type,
      number: doc.number ?? "",
      document_date: doc.document_date,
      warehouse_id: doc.warehouse_id ? String(doc.warehouse_id) : "",
      destination_warehouse_id: doc.destination_warehouse_id ? String(doc.destination_warehouse_id) : "",
      partner_id: doc.partner_id ? String(doc.partner_id) : "",
      currency_code: doc.currency_code ?? "RUB_PMR",
      exchange_rate: doc.exchange_rate ?? "1",
      note: doc.note ?? ""
    };
    setHeader(nextHeader);
    setSavedHeader(nextHeader);
    if (doc.partner_id) {
      api.partner(doc.partner_id).then((partner) => {
        setPartners((current) => current.some((item) => item.id === partner.id) ? current : [partner, ...current]);
      }).catch(() => undefined);
    }
  }

  function load() {
    if (!documentId) return;
    api.document(documentId).then((doc) => { draft.clear(); applyDocument(doc); }).catch((exc) => setError(String(exc)));
    api.documentRevisions(documentId).then(setRevisions).catch(() => setRevisions([]));
  }

  useEffect(() => {
    let active = true;
    if (documentId) {
      api.document(documentId)
        .then((doc) => {
          if (active) applyDocument(doc);
        })
        .catch((exc) => {
          if (active) setError(String(exc));
        });
      api.documentRevisions(documentId)
        .then((rows) => active && setRevisions(rows))
        .catch(() => active && setRevisions([]));
    }
    api.warehouses().then((rows) => active && setWarehouses(rows)).catch(() => active && setWarehouses([]));
    api.currencies().then((rows) => active && setCurrencies(rows)).catch(() => active && setCurrencies([]));
    return () => {
      active = false;
    };
  }, [documentId]);

  useEffect(() => {
    let active = true;
    setProductOptionsLoading(true);
    const timeout = window.setTimeout(() => {
      api.productOptions(productSearch)
        .then((rows) => {
          if (!active) return;
          setProductOptionsLoading(false);
          setProducts((current) => {
            const selected = current.find((item) => String(item.id) === productId);
            return selected && !rows.some((item) => item.id === selected.id) ? [selected, ...rows] : rows;
          });
        })
        .catch(() => {
          if (!active) return;
          setProductOptionsLoading(false);
          setProducts([]);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [productSearch]);

  useEffect(() => {
    if (header.document_type === "transfer" || header.document_type === "adjustment") {
      setPartners([]);
      return;
    }
    let active = true;
    const timeout = window.setTimeout(() => {
      api.partnerOptions(partnerSearch, header.document_type === "incoming" ? "supplier" : "customer")
        .then((rows) => {
          if (!active) return;
          setPartners((current) => {
            const selected = current.find((item) => String(item.id) === header.partner_id);
            return selected && !rows.some((item) => item.id === selected.id) ? [selected, ...rows] : rows;
          });
        })
        .catch(() => active && setPartners([]));
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [header.document_type, partnerSearch]);

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
    setProductSearch(product ? `${product.name}${product.sku ? ` (${product.sku})` : ""}` : "");
    setProductOptionsOpen(false);
    setActiveProductIndex(-1);
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

  function headerPayload() {
    return {
      document_type: header.document_type,
      number: header.number || null,
      document_date: header.document_date,
      warehouse_id: header.warehouse_id ? Number(header.warehouse_id) : null,
      destination_warehouse_id: header.destination_warehouse_id ? Number(header.destination_warehouse_id) : null,
      partner_id: header.partner_id ? Number(header.partner_id) : null,
      currency_code: isIncoming ? header.currency_code : "RUB_PMR",
      exchange_rate: isIncoming ? header.exchange_rate : "1",
      note: header.note || null
    };
  }

  function validateHeader() {
    const errors: Record<string, string> = {};
    if (!header.document_date) errors.document_date = t("selectDate");
    if (!header.warehouse_id) errors.warehouse_id = t("selectWarehouse");
    if ((header.document_type === "incoming" || header.document_type === "outgoing") && !header.partner_id) errors.partner_id = t("selectPartner");
    if (header.document_type === "transfer") {
      if (!header.destination_warehouse_id) errors.destination_warehouse_id = t("selectDestinationWarehouse");
      else if (header.destination_warehouse_id === header.warehouse_id) errors.destination_warehouse_id = t("differentWarehousesRequired");
    }
    if (isIncoming && (!Number.isFinite(Number(header.exchange_rate)) || Number(header.exchange_rate) <= 0)) errors.exchange_rate = t("invalidExchangeRate");
    setValidationErrors(errors);
    const first = Object.values(errors)[0];
    if (first) {
      setError(first);
      showToast("warning", first);
    }
    return !first;
  }

  function persistHeader() {
    return api.updateDocument(documentId, headerPayload()).then((doc) => {
      draft.clear();
      applyDocument(doc);
      return doc;
    });
  }

  function resetLineEntry() {
    setEditingDraftLineId(null);
    setEditingCorrectionLineId(null);
    setProductId("");
    setProductSearch("");
    setProductOptionsOpen(false);
    setActiveProductIndex(-1);
    setQuantity("1");
    setPrice("0");
    setError("");
  }

  function addLine() {
    if (savingLine || !can("documents.update")) return;
    setError("");
    if (!validateHeader()) return;
    if (!Number.isFinite(Number(quantity)) || Number(quantity) <= 0) {
      setError(t("invalidQuantity"));
      showToast("warning", t("invalidQuantity"));
      return;
    }
    if (!Number.isFinite(Number(price)) || Number(price) < 0) {
      setError(t("invalidPrice"));
      showToast("warning", t("invalidPrice"));
      return;
    }
    if (isIncoming && Number(header.exchange_rate) <= 0) {
      setError(t("invalidExchangeRate"));
      showToast("warning", t("invalidExchangeRate"));
      return;
    }
    if (!productId) {
      setError(t("selectProduct"));
      showToast("warning", t("selectProduct"));
      return;
    }
    if (correctionMode) {
      const product = products.find((item) => item.id === Number(productId));
      const existingLine = editingCorrectionLineId === null
        ? undefined
        : correctionLines.find((line) => line.id === editingCorrectionLineId);
      const foreignPrice = isIncoming ? Number(price) : null;
      const basePrice = isIncoming ? Number(price) * Number(header.exchange_rate || 1) : Number(price);
      const lineId = editingCorrectionLineId ?? (Math.min(0, ...correctionLines.map((line) => line.id)) - 1);
      const correctedLine: DocumentLine = {
          id: lineId,
          document_id: documentId,
          product_id: Number(productId),
          product_name: product?.name ?? existingLine?.product_name,
          quantity: Number(quantity).toFixed(3),
          price: basePrice.toFixed(2),
          foreign_price: foreignPrice === null ? null : foreignPrice.toFixed(2),
          line_total: (Number(quantity) * basePrice).toFixed(2),
          foreign_line_total: foreignPrice === null ? null : (Number(quantity) * foreignPrice).toFixed(2)
      };
      setCorrectionLines((current) => editingCorrectionLineId === null
        ? [...current, correctedLine]
        : current.map((line) => line.id === editingCorrectionLineId ? correctedLine : line));
      resetLineEntry();
      showToast("success", t(editingCorrectionLineId === null ? "lineAddedToCorrection" : "lineUpdatedInCorrection"));
      return;
    }
    const payload = { product_id: Number(productId), quantity, price: isIncoming ? "0" : price, foreign_price: isIncoming ? price : null };
    setSavingLine(true);
    persistHeader()
      .then(() => editingDraftLineId === null
        ? api.addDocumentLine(documentId, payload)
        : api.updateDocumentLine(documentId, editingDraftLineId, payload))
      .then(() => api.document(documentId))
      .then((doc) => {
        draft.clear();
        applyDocument(doc);
        showToast("success", t("saved"));
        resetLineEntry();
      })
      .catch(handleError)
      .finally(() => setSavingLine(false));
  }

  function saveHeader() {
    setError("");
    if (!validateHeader()) return;
    persistHeader()
      .then((doc) => {
        showToast("success", t("saved"));
        load();
      })
      .catch(handleError);
  }

  function beginCorrection() {
    if (!document?.lines) return;
    resetLineEntry();
    setCorrectionLines(document.lines.map((line) => ({ ...line })));
    setCorrectionReason("");
    setEditingCorrectionLineId(null);
    setCorrectionMode(true);
    setError("");
  }

  function discardCorrection() {
    draft.clear();
    if (document) applyDocument(document);
    setCorrectionLines([]);
    setCorrectionReason("");
    setCorrectionMode(false);
    resetLineEntry();
    setError("");
  }

  async function applyCorrection() {
    if (lineDraftDirty) {
      setError(t("finishLineBeforePosting"));
      showToast("warning", t("finishLineBeforePosting"));
      return;
    }
    if (!validateHeader()) return;
    const reason = correctionReason.trim();
    if (reason.length < 3) {
      setError(t("correctionReasonRequired"));
      showToast("warning", t("correctionReasonRequired"));
      return;
    }
    if (correctionLines.length === 0) {
      setError(t("documentHasNoLines"));
      showToast("warning", t("documentHasNoLines"));
      return;
    }
    if (!(await ask({ message: `${t("repostConfirm")} ${header.number || `#${documentId}`}`, confirmLabel: t("applyCorrection") }))) return;
    const rate = Number(header.exchange_rate || 1);
    api.repostDocument(documentId, {
      ...headerPayload(),
      reason,
      lines: correctionLines.map((line) => ({
        product_id: line.product_id,
        quantity: line.quantity,
        price: isIncoming ? "0" : line.price,
        foreign_price: isIncoming ? (line.foreign_price ?? (Number(line.price) / rate).toFixed(2)) : null
      }))
    }).then((doc) => {
      draft.clear();
      applyDocument(doc);
      setCorrectionMode(false);
      setCorrectionLines([]);
      setCorrectionReason("");
      setEditingCorrectionLineId(null);
      showToast("success", t("repostedSuccess"));
      load();
    }).catch(handleError);
  }

  async function post() {
    setError("");
    if (savingLine) return;
    if (lineDraftDirty) {
      setError(t("finishLineBeforePosting"));
      showToast("warning", t("finishLineBeforePosting"));
      return;
    }
    if (!validateHeader()) return;
    if (!(await ask({ message: `${t("postConfirm")} ${header.number || `#${documentId}`}`, confirmLabel: t("post") }))) return;
    persistHeader()
      .then(() => api.postDocument(documentId))
      .then((doc) => {
        draft.clear();
        setDocument(doc);
        showToast("success", t("postedSuccess"));
        load();
      })
      .catch(handleError);
  }

  async function cancel() {
    setError("");
    if (!(await ask({ message: `${t("cancelConfirm")} ${header.number || `#${documentId}`}`, confirmLabel: t("cancel"), danger: true }))) return;
    api.cancelDocument(documentId).then((doc) => {
      draft.clear();
      setDocument(doc);
      showToast("success", t("cancelledSuccess"));
      load();
    }).catch(handleError);
  }

  async function deleteDraft() {
    setError("");
    if (!(await ask({ message: `${t("deleteDraftConfirm")} ${header.number || `#${documentId}`}`, confirmLabel: t("deleteDraft"), danger: true }))) return;
    api.deleteDocument(documentId).then(() => {
      draft.clear();
      showToast("success", t("deleteDraft"));
      allowExitRef.current = true;
      window.location.href = "/documents";
    }).catch(handleError);
  }

  async function deleteLine(lineId: number) {
    if (savingLine) return;
    setError("");
    if (correctionMode) {
      setCorrectionLines((current) => current.filter((line) => line.id !== lineId));
      if (editingCorrectionLineId === lineId) resetLineEntry();
      return;
    }
    if (!(await ask({ message: t("deleteLineConfirm"), confirmLabel: t("deleteLine"), danger: true }))) return;
    api.deleteDocumentLine(documentId, lineId).then(() => {
      if (editingDraftLineId === lineId) resetLineEntry();
      showToast("success", t("deleteLine"));
      load();
    }).catch(handleError);
  }

  async function editLine(line: DocumentLine) {
    if (savingLine || !can("documents.update")) return;
    if ((correctionMode ? editingCorrectionLineId : editingDraftLineId) === line.id) return;
    if (lineDraftDirty && !(await ask({ message: t("unsavedLineDraftConfirm"), confirmLabel: t("editLine") }))) return;
    if (correctionMode) setEditingCorrectionLineId(line.id);
    else setEditingDraftLineId(line.id);
    setProductId(String(line.product_id));
    setProductSearch(line.product_name ?? products.find((item) => item.id === line.product_id)?.name ?? "");
    setQuantity(String(line.quantity));
    setPrice(String(isIncoming ? (line.foreign_price ?? (Number(line.price) / Number(header.exchange_rate || 1)).toFixed(2)) : line.price));
    setProductOptionsOpen(false);
    setActiveProductIndex(-1);
    setError("");
    window.requestAnimationFrame(() => productInputRef.current?.focus());
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
  const isEditable = (isDraft || correctionMode) && !savingLine;
  const editingLineId = correctionMode ? editingCorrectionLineId : editingDraftLineId;
  const editingLine = (correctionMode ? correctionLines : document?.lines ?? []).find((line) => line.id === editingLineId);
  const displayedLines = correctionMode ? correctionLines : (document?.lines ?? []);
  const displayedTotal = correctionMode
    ? correctionLines.reduce((sum, line) => sum + Number(line.line_total), 0).toFixed(2)
    : (document?.total_amount ?? "0");
  const displayedForeignTotal = correctionMode
    ? correctionLines.reduce((sum, line) => sum + Number(line.foreign_line_total ?? line.line_total), 0).toFixed(2)
    : (document?.foreign_total_amount ?? "0");
  const readOnlyReason = isPosted && !correctionMode ? t("documentPostedReadOnly") : isCancelled ? t("documentCancelledReadOnly") : "";

  return (
    <div className="document-workspace">
      {dialog}
      <div className="document-heading">
        <div>
          <Link className="document-back" to="/documents">← {t("backToDocuments")}</Link>
          <h1>{formatCode(header.document_type, t)} {header.number || `#${documentId}`}</h1>
          <div className="document-heading-meta"><StatusBadge status={document?.status} label={formatCode(document?.status, t)} />{document?.posting_version ? <span data-testid="document-posting-version">v{document.posting_version}</span> : null}</div>
        </div>
        {hasUnsavedChanges ? <span className="document-unsaved">{t("unsavedChanges")}</span> : null}
      </div>
      <div className="document-actions" aria-label={t("actions")}>
        <button className="button" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isDraft || savingLine} onClick={saveHeader}>{t("save")}</button>
        <button data-testid="document-post" className="button primary" title={!can("documents.post") ? t("noPermission") : ""} disabled={!can("documents.post") || !isDraft || savingLine} onClick={post}>{t("post")}</button>
        {isPosted && !correctionMode ? <button data-testid="document-correction-start" className="button primary" title={!can("documents.update") || !can("documents.post") ? t("noPermission") : ""} disabled={!can("documents.update") || !can("documents.post")} onClick={beginCorrection}>{t("correctDocument")}</button> : null}
        {correctionMode ? <button data-testid="document-correction-apply" className="button primary" onClick={applyCorrection}>{t("applyCorrection")}</button> : null}
        {correctionMode ? <button className="button" onClick={discardCorrection}>{t("discardCorrection")}</button> : null}
        <button className="button" title={!can("documents.read") ? t("noPermission") : ""} disabled={!can("documents.read")} onClick={print}>{t("print")}</button>
        <details className="document-more-actions">
          <summary className="button">{t("moreActions")}</summary>
          <div className="document-more-menu">
            <CopyDocumentButton documentId={documentId} documentNumber={document?.number} hasUnsavedChanges={hasUnsavedChanges} disabled={!document || savingLine} onCopied={(copied) => {
              allowExitRef.current = true;
              navigate(`/documents/${copied.id}`);
            }} />
            <button className="button" title={!can("documents.read") ? t("noPermission") : ""} disabled={!can("documents.read")} onClick={downloadPdf}>{t("downloadPdf")}</button>
            <button className="button" title={!can("documents.cancel") ? t("noPermission") : ""} disabled={!can("documents.cancel") || !isPosted || correctionMode} onClick={cancel}>{t("cancel")}</button>
            <button className="button" title={!can("documents.delete") ? t("noPermission") : ""} disabled={!can("documents.delete") || !isDraft || savingLine} onClick={deleteDraft}>{t("deleteDraft")}</button>
          </div>
        </details>
      </div>
      <DraftRecoveryNotice draft={draft} />
      {document ? <DocumentRelations document={document} /> : null}
      {error ? <div className="panel error-panel">{error}</div> : null}
      {readOnlyReason ? <div className="panel" style={{ padding: 10, color: "#52616f", fontSize: 13 }}>{readOnlyReason}</div> : null}
      {correctionMode ? (
        <div className="panel form-grid" style={{ borderColor: "#d89b2b" }}>
          <div className="field" style={{ gridColumn: "1 / -1" }}>
            <label>{t("correctionReason")}</label>
            <input data-testid="document-correction-reason" value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder={t("correctionReasonPlaceholder")} autoFocus />
          </div>
          <div style={{ gridColumn: "1 / -1", color: "#52616f", fontSize: 13 }}>{t("atomicCorrectionHint")}</div>
        </div>
      ) : null}
      <section className="document-section panel" aria-label={t("documentDetails")}>
        <h2>{t("documentDetails")}</h2>
        <div className="document-header-grid form-grid">
        <div className="field">
          <label>{t("type")}</label>
          <select
            value={header.document_type}
            onChange={(event) => setDocumentType(event.target.value)}
            disabled={!isEditable}
          >
            <option value="incoming">{t("incoming")}</option>
            <option value="outgoing">{t("outgoing")}</option>
            <option value="adjustment">{t("adjustment")}</option>
            <option value="transfer">{t("transfer")}</option>
          </select>
        </div>
        <div className="field"><label>{t("number")}</label><input value={header.number} onChange={(event) => setHeader({ ...header, number: event.target.value })} disabled={!isEditable} /></div>
        <div className="field"><label htmlFor="document-date">{t("date")}</label><input id="document-date" type="date" value={header.document_date} onChange={(event) => setHeader({ ...header, document_date: event.target.value })} disabled={!isEditable} aria-invalid={Boolean(validationErrors.document_date)} />{validationErrors.document_date ? <small className="field-error">{validationErrors.document_date}</small> : null}</div>
        {header.document_type !== "transfer" && header.document_type !== "adjustment" ? <div className="field"><label>{t("search")}: {t("partner")}</label><input value={partnerSearch} onChange={(event) => setPartnerSearch(event.target.value)} disabled={!isEditable} /></div> : null}
        <div className="field">
          <label htmlFor="document-warehouse">{header.document_type === "transfer" ? t("sourceWarehouse") : t("warehouse")}</label>
          <select id="document-warehouse" value={header.warehouse_id} onChange={(event) => setHeader({ ...header, warehouse_id: event.target.value })} disabled={!isEditable} aria-invalid={Boolean(validationErrors.warehouse_id)}>
            <option value="">{t("notSelected")}</option>
            {warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
          </select>
          {validationErrors.warehouse_id ? <small className="field-error">{validationErrors.warehouse_id}</small> : null}
        </div>
        {header.document_type === "transfer" ? (
          <div className="field">
            <label htmlFor="document-destination-warehouse">{t("destinationWarehouse")}</label>
            <select id="document-destination-warehouse" value={header.destination_warehouse_id} onChange={(event) => setHeader({ ...header, destination_warehouse_id: event.target.value })} disabled={!isEditable} aria-invalid={Boolean(validationErrors.destination_warehouse_id)}>
              <option value="">{t("notSelected")}</option>
              {warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>)}
            </select>
            {validationErrors.destination_warehouse_id ? <small className="field-error">{validationErrors.destination_warehouse_id}</small> : null}
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="document-partner">{t("partner")}</label>
          <select id="document-partner" value={header.partner_id} onChange={(event) => setHeader({ ...header, partner_id: event.target.value })} disabled={!isEditable || header.document_type === "transfer" || header.document_type === "adjustment"} aria-invalid={Boolean(validationErrors.partner_id)}>
            <option value="">{t("notSelected")}</option>
            {filteredPartners.map((partner) => <option key={partner.id} value={partner.id}>{partner.name} - {formatCode(partner.partner_type, t)}</option>)}
          </select>
          {validationErrors.partner_id ? <small className="field-error">{validationErrors.partner_id}</small> : null}
        </div>
        {header.document_type === "incoming" ? (
          <>
            <div className="field">
              <label>{t("currency")}</label>
              <select data-testid="document-currency" value={header.currency_code} onChange={(event) => setCurrency(event.target.value)} disabled={!isEditable}>
                {currencies.map((currency) => <option key={currency.code} value={currency.code}>{currency.code} - {currency.name}</option>)}
              </select>
            </div>
            <div className="field"><label htmlFor="document-exchange-rate">{t("exchangeRate")}</label><input id="document-exchange-rate" data-testid="document-exchange-rate" value={header.exchange_rate} onChange={(event) => setHeader({ ...header, exchange_rate: event.target.value })} disabled={!isEditable || header.currency_code === "RUB_PMR"} aria-invalid={Boolean(validationErrors.exchange_rate)} />{validationErrors.exchange_rate ? <small className="field-error">{validationErrors.exchange_rate}</small> : null}</div>
          </>
        ) : null}
        <div className="field document-note"><label htmlFor="document-note">{t("note")}</label><input id="document-note" value={header.note} onChange={(event) => setHeader({ ...header, note: event.target.value })} disabled={!isEditable} /></div>
        </div>
      </section>

      <section className="document-section document-lines-section panel" aria-label={t("documentLines")}>
        <div className="document-section-title"><h2>{t("documentLines")}</h2><span>{displayedLines.length}</span></div>
        {editingLine ? <div data-testid="document-line-editing" role="status" style={{ marginBottom: 10 }}><strong>{t("editingLine")}</strong>: {editingLine.product_name}</div> : null}
        <div className="document-line-entry form-grid">
        <div className="field document-product-picker" onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setProductOptionsOpen(false); }}>
          <label htmlFor="document-product-search">{t("product")}</label>
          <input
            id="document-product-search"
            ref={productInputRef}
            data-testid="document-product"
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={productOptionsOpen}
            aria-controls="document-product-options"
            aria-activedescendant={productOptionsOpen && products[activeProductIndex] ? `document-product-option-${products[activeProductIndex].id}` : undefined}
            value={productSearch}
            placeholder={t("productSearch")}
            onFocus={() => setProductOptionsOpen(true)}
            onChange={(event) => {
              setProductSearch(event.target.value);
              setProductId("");
              setPrice("0");
              setActiveProductIndex(-1);
              setProductOptionsOpen(true);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setProductOptionsOpen(true);
                setActiveProductIndex((current) => Math.min(current + 1, products.length - 1));
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setProductOptionsOpen(true);
                setActiveProductIndex((current) => Math.max(0, current - 1));
              } else if (event.key === "Enter" && productOptionsOpen && products.length) {
                event.preventDefault();
                setSelectedProduct(String(products[Math.max(0, activeProductIndex)].id));
              } else if (event.key === "Escape") {
                setProductOptionsOpen(false);
              }
            }}
            disabled={!isEditable}
          />
          {productOptionsOpen && isEditable ? (
            <div id="document-product-options" className="document-product-options" role="listbox" aria-label={t("product")}>
              {productOptionsLoading ? <div className="document-product-option-empty">{t("loading")}</div> : products.length ? products.map((product, index) => (
                <button
                  key={product.id}
                  id={`document-product-option-${product.id}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeProductIndex}
                  className={index === activeProductIndex ? "active" : ""}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => setSelectedProduct(String(product.id))}
                >
                  <span>{product.name}</span>{product.sku ? <small>{product.sku}</small> : null}
                </button>
              )) : <div className="document-product-option-empty">Товары не найдены</div>}
            </div>
          ) : null}
        </div>
        <div className="field"><label htmlFor="document-line-quantity">{t("quantity")}</label><input id="document-line-quantity" data-testid="document-line-quantity" inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} disabled={!isEditable} /></div>
        <div className="field"><label htmlFor="document-line-price">{isIncoming ? t("foreignPrice") : t("price")}</label><input id="document-line-price" data-testid="document-line-price" inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} disabled={!isEditable} /></div>
        <div className="field"><label>{isIncoming ? t("foreignSum") : t("sum")}</label><input value={lineSum.toFixed(2)} readOnly /></div>
        {isIncoming ? <div className="field"><label>{t("baseSum")}</label><input value={baseLineSum.toFixed(2)} readOnly /></div> : null}
        <div className="field"><label>{t("stockBalance")}</label><input value={stockBalance ?? ""} readOnly /></div>
        <div className="field"><label>&nbsp;</label><button data-testid="document-line-add" className="button primary" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isEditable} onClick={addLine}>{t(editingLineId === null ? "addLine" : "saveLine")}</button></div>
        {editingLineId !== null || lineDraftDirty ? <div className="field"><label>&nbsp;</label><button data-testid="document-line-edit-cancel" className="button" disabled={savingLine} onClick={resetLineEntry}>{t("cancelLineEdit")}</button></div> : null}
        </div>
      {salePriceReview ? (
        <div data-testid="sale-price-review" className="panel" style={{ padding: 10, color: salePriceReview.priceReviewRequired ? "#8b1e16" : "#6b5200", background: salePriceReview.priceReviewRequired ? "#fff1f0" : "#fffbea", borderColor: salePriceReview.priceReviewRequired ? "#e6a29c" : "#e8cf6a", fontSize: 13 }}>
          {salePriceReview.costChanged ? <div>{t(salePriceReview.direction === "first" ? "firstPurchaseCost" : salePriceReview.direction === "higher" ? "purchaseCostHigher" : "purchaseCostLower")} {salePriceReview.previousPurchaseCost !== null ? `${t("latestPurchaseCost")}: ${formatMoney(salePriceReview.previousPurchaseCost.toFixed(2))}; ` : ""}{t("newBasePurchasePrice")}: {formatMoney(salePriceReview.baseUnitCost.toFixed(2))}.</div> : null}
          {salePriceReview.priceReviewRequired ? <div><strong>{t("salePriceReviewHint")}</strong> {t("proposedMarkup")}: {salePriceReview.markupPercent === null ? "-" : `${salePriceReview.markupPercent.toFixed(2)}%`}; {t("minimumSalePrice")}: {formatMoney(salePriceReview.minimumSalePrice.toFixed(2))}.</div> : <div>{t("proposedMarkup")}: {salePriceReview.markupPercent?.toFixed(2)}%. {t("priceMeetsMarkup")}.</div>}
        </div>
      ) : null}

      <DataTable
        rows={displayedLines}
        emptyMessage={t("noLines")}
        searchable
        columns={[
          { key: "product_name", header: t("product"), sortable: true },
          { key: "quantity", header: t("quantity"), sortable: true },
          ...(header.document_type === "incoming" ? [{ key: "foreign_price", header: t("foreignPrice"), sortable: true, render: (row: any) => row.foreign_price ? `${formatMoney(row.foreign_price)} ${header.currency_code}` : "" }] : []),
          { key: "price", header: t("price"), sortable: true, render: (row) => formatMoney(row.price) },
          ...(header.document_type === "incoming" ? [{ key: "foreign_line_total", header: t("foreignSum"), sortable: true, render: (row: any) => row.foreign_line_total ? `${formatMoney(row.foreign_line_total)} ${header.currency_code}` : "" }] : []),
          { key: "line_total", header: t("sum"), sortable: true, render: (row) => formatMoney(row.line_total) },
          {
            key: "actions",
            header: t("actions"),
            render: (row) => (
              <div style={{ display: "flex", gap: 6 }}>
                {isDraft || correctionMode ? <button data-testid={`document-line-edit-${row.id}`} className="button" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isEditable} onClick={() => editLine(row)}>{t("editLine")}</button> : null}
                <button className="button" title={!can("documents.update") ? t("noPermission") : ""} disabled={!can("documents.update") || !isEditable} onClick={() => deleteLine(row.id)}>{t("deleteLine")}</button>
              </div>
            )
          }
        ]}
      />
      <div className="document-total-bar">
        <span>{t("total")}</span><strong>{formatMoney(displayedTotal)}</strong>
        {isIncoming ? <small>{t("foreignTotal")}: {formatMoney(displayedForeignTotal)} {header.currency_code}</small> : null}
      </div>
      </section>
      {revisions.length ? (
        <div className="panel" style={{ padding: 12 }}>
          <h2 style={{ fontSize: 16, margin: "0 0 8px" }}>{t("documentHistory")}</h2>
          <div style={{ display: "grid", gap: 6 }}>
            {revisions.map((revision) => (
              <div key={revision.id} style={{ display: "flex", flexWrap: "wrap", gap: 10, borderTop: "1px solid #dce2e8", paddingTop: 7 }}>
                <strong>v{revision.version}</strong>
                <span>{revision.reason}</span>
                {revision.actor_name ? <span>{revision.actor_name}</span> : null}
                <span style={{ color: "#667788" }}>{new Date(revision.created_at).toLocaleString("ru-RU")}</span>
                <span style={{ marginLeft: "auto" }}>{t("total")}: {formatMoney(revision.snapshot.total_amount ?? "0")}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
