import { useEffect, useMemo, useState } from "react";

import { DataTable } from "../components/DataTable";
import { PageScaffold } from "../components/PageScaffold";
import { useAuth } from "../auth";
import { formatMoney } from "../format";
import { useI18n } from "../i18n";
import { Product, ProductGroup, api } from "../lib/api";

const PAGE_SIZE = 25;
type ProductSort = "name" | "sku" | "base_price" | "created_at" | "is_active";

export function Products() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [rows, setRows] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [catalogTotal, setCatalogTotal] = useState(0);
  const [directGroupCounts, setDirectGroupCounts] = useState(new Map<number, number>());
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<ProductSort>("name");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [groups, setGroups] = useState<ProductGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState("");
  const [groupName, setGroupName] = useState("");
  const [groupParentId, setGroupParentId] = useState("");
  const [groupEditingId, setGroupEditingId] = useState<number | null>(null);
  const [groupFormOpen, setGroupFormOpen] = useState(false);
  const [basePrice, setBasePrice] = useState("0");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [productFormOpen, setProductFormOpen] = useState(false);
  const [error, setError] = useState("");

  function loadGroups() {
    api.productGroups().then(setGroups).catch(() => setGroups([]));
  }

  function refresh() {
    setRefreshVersion((current) => current + 1);
    loadGroups();
  }

  const groupIds = useMemo(() => new Set(groups.map((group) => group.id)), [groups]);
  const rootGroups = useMemo(
    () => groups.filter((group) => !group.parent_id || !groupIds.has(group.parent_id)),
    [groupIds, groups]
  );
  const childrenByParent = useMemo(() => {
    const result = new Map<number, ProductGroup[]>();
    groups.forEach((group) => {
      if (!group.parent_id) return;
      result.set(group.parent_id, [...(result.get(group.parent_id) ?? []), group]);
    });
    return result;
  }, [groups]);

  const descendantsByGroup = useMemo(() => {
    const result = new Map<number, Set<number>>();

    function collectDescendants(groupId: number, lineage: Set<number>): Set<number> {
      const cached = result.get(groupId);
      if (cached) return cached;

      const descendants = new Set<number>();
      if (lineage.has(groupId)) return descendants;

      const nextLineage = new Set(lineage).add(groupId);
      (childrenByParent.get(groupId) ?? []).forEach((child) => {
        if (nextLineage.has(child.id)) return;
        descendants.add(child.id);
        collectDescendants(child.id, nextLineage).forEach((id) => descendants.add(id));
      });
      result.set(groupId, descendants);
      return descendants;
    }

    groups.forEach((group) => collectDescendants(group.id, new Set()));
    return result;
  }, [childrenByParent, groups]);

  const groupOptions = useMemo(() => {
    const result: Array<{ group: ProductGroup; depth: number }> = [];
    const visited = new Set<number>();

    function visit(group: ProductGroup, depth: number) {
      if (visited.has(group.id)) return;
      visited.add(group.id);
      result.push({ group, depth });
      (childrenByParent.get(group.id) ?? []).forEach((child) => visit(child, depth + 1));
    }

    rootGroups.forEach((group) => visit(group, 0));
    groups.forEach((group) => visit(group, 0));
    return result;
  }, [childrenByParent, groups, rootGroups]);

  const productCountByGroup = useMemo(() => {
    const result = new Map<number, number>();
    groups.forEach((group) => {
      let count = directGroupCounts.get(group.id) ?? 0;
      (descendantsByGroup.get(group.id) ?? new Set()).forEach((id) => {
        count += directGroupCounts.get(id) ?? 0;
      });
      result.set(group.id, count);
    });
    return result;
  }, [descendantsByGroup, directGroupCounts, groups]);

  const selectedGroupIds = useMemo(
    () => selectedGroupId === null ? undefined : [selectedGroupId, ...(descendantsByGroup.get(selectedGroupId) ?? [])],
    [descendantsByGroup, selectedGroupId]
  );
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const selectedGroup = groups.find((group) => group.id === selectedGroupId);

  function resetForm() {
    setSku("");
    setName("");
    setGroupId(selectedGroupId !== null ? String(selectedGroupId) : "");
    setBasePrice("0");
    setEditingId(null);
  }

  function save() {
    if (!name.trim()) return;
    const payload = { sku: sku || null, name: name.trim(), group_id: groupId ? Number(groupId) : null, base_price: basePrice, is_active: true };
    const request = editingId ? api.updateProduct(editingId, payload) : api.createProduct(payload);
    request.then(() => {
      resetForm();
      setProductFormOpen(false);
      setError("");
      refresh();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreateProductError")));
  }

  function edit(row: Product) {
    setEditingId(row.id);
    setSku(row.sku ?? "");
    setName(row.name);
    setGroupId(row.group_id ? String(row.group_id) : "");
    setBasePrice(String(row.base_price ?? "0"));
    setProductFormOpen(true);
  }

  function resetGroupForm() {
    setGroupName("");
    setGroupParentId("");
    setGroupEditingId(null);
  }

  function saveGroup() {
    const nextName = groupName.trim();
    if (!nextName) return;
    const payload = { name: nextName, parent_id: groupParentId ? Number(groupParentId) : null };
    const request = groupEditingId ? api.updateProductGroup(groupEditingId, payload) : api.createProductGroup(payload);
    request.then(() => {
      resetGroupForm();
      setGroupFormOpen(false);
      setError("");
      refresh();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("apiCreateProductGroupError")));
  }

  function editGroup(row: ProductGroup) {
    setGroupEditingId(row.id);
    setGroupName(row.name);
    setGroupParentId(row.parent_id ? String(row.parent_id) : "");
    setGroupFormOpen(true);
  }

  function removeGroup(row: ProductGroup) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deleteProductGroup(row.id).then(() => {
      if (selectedGroupId === row.id) setSelectedGroupId(null);
      refresh();
    }).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  function remove(row: Product) {
    if (!window.confirm(t("deleteConfirm"))) return;
    api.deleteProduct(row.id).then(refresh).catch((exc) => setError(exc instanceof Error ? exc.message : t("deleteError")));
  }

  function renderCategoryNode(group: ProductGroup, depth = 0, lineage = new Set<number>()) {
    if (lineage.has(group.id)) return null;

    const nextLineage = new Set(lineage).add(group.id);
    const children = (childrenByParent.get(group.id) ?? []).filter((child) => !nextLineage.has(child.id));
    const isSelected = selectedGroupId === group.id;
    const containsSelected = selectedGroupId !== null && (descendantsByGroup.get(group.id)?.has(selectedGroupId) ?? false);
    const groupButton = (
      <button className={isSelected ? "selected" : ""} onClick={(event) => { event.preventDefault(); setSelectedGroupId(group.id); setPage(0); }}>
        <span>{group.name}</span><b>{productCountByGroup.get(group.id) ?? 0}</b>
      </button>
    );
    const actions = (
      <span className="category-actions">
        <button aria-label={t("edit")} title={!can("products.update") ? t("noPermission") : t("edit")} disabled={!can("products.update")} onClick={(event) => { event.preventDefault(); editGroup(group); }}>✎</button>
        <button aria-label={t("delete")} title={!can("products.delete") ? t("noPermission") : t("delete")} disabled={!can("products.delete")} onClick={(event) => { event.preventDefault(); removeGroup(group); }}>×</button>
      </span>
    );

    if (children.length === 0) {
      return (
        <div className={`category-child ${depth === 0 ? "category-root" : ""} ${isSelected ? "selected" : ""}`} key={group.id}>
          {groupButton}
          {actions}
        </div>
      );
    }

    return (
      <details className="category-branch" key={group.id} open={isSelected || containsSelected ? true : undefined}>
        <summary>{groupButton}{actions}</summary>
        <div className="category-children">
          {children.map((child) => renderCategoryNode(child, depth + 1, nextLineage))}
        </div>
      </details>
    );
  }

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    api.productGroupCounts().then((result) => {
      setCatalogTotal(result.total);
      setDirectGroupCounts(new Map(result.items.map((item) => [item.group_id, item.count])));
    }).catch(() => {
      setCatalogTotal(0);
      setDirectGroupCounts(new Map());
    });
  }, [refreshVersion]);

  useEffect(() => {
    let active = true;
    const timeout = window.setTimeout(() => {
      api.products({
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        search,
        sort_by: sortBy,
        sort_order: sortOrder,
        group_ids: selectedGroupIds
      }).then((result) => {
        if (!active) return;
        if (result.total > 0 && page * PAGE_SIZE >= result.total) {
          setPage(Math.max(0, Math.ceil(result.total / PAGE_SIZE) - 1));
          return;
        }
        setRows(result.items);
        setTotal(result.total);
        setError("");
      }).catch((exc) => {
        if (!active) return;
        setRows([]);
        setTotal(0);
        setError(exc instanceof Error ? exc.message : t("apiLoadProductsError"));
      });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timeout);
    };
  }, [page, refreshVersion, search, selectedGroupIds, sortBy, sortOrder, t]);

  return (
    <PageScaffold title={t("products")}>
      {error ? <div className="panel error-panel products-error">{error}</div> : null}
      <div className="products-workspace">
        <aside className="panel products-categories">
          <div className="products-section-header">
            <div><strong>{t("productCategories")}</strong><span>{groups.length}</span></div>
            <button className="button" title={!can("products.create") ? t("noPermission") : ""} disabled={!can("products.create")} onClick={() => { resetGroupForm(); setGroupFormOpen((open) => !open); }}>+ {t("create")}</button>
          </div>

          {groupFormOpen ? (
            <div className="products-compact-form">
              <div className="field"><label>{t("name")}</label><input autoFocus value={groupName} onChange={(event) => setGroupName(event.target.value)} /></div>
              <div className="field">
                <label>{t("parentCategory")}</label>
                <select value={groupParentId} onChange={(event) => setGroupParentId(event.target.value)}>
                  <option value="">{t("rootCategory")}</option>
                  {groupOptions
                    .filter(({ group }) => group.id !== groupEditingId && !(groupEditingId !== null && descendantsByGroup.get(groupEditingId)?.has(group.id)))
                    .map(({ group, depth }) => <option key={group.id} value={group.id}>{`${"— ".repeat(depth)}${group.name}`}</option>)}
                </select>
              </div>
              <div className="products-form-actions">
                <button className="button primary" disabled={!can(groupEditingId ? "products.update" : "products.create")} onClick={saveGroup}>{groupEditingId ? t("save") : t("create")}</button>
                <button className="button" onClick={() => { resetGroupForm(); setGroupFormOpen(false); }}>{t("cancel")}</button>
              </div>
            </div>
          ) : null}

          <div className="category-tree">
            <button className={`category-all ${selectedGroupId === null ? "selected" : ""}`} onClick={() => { setSelectedGroupId(null); setPage(0); }}>
              <span>{t("allProducts")}</span><b>{catalogTotal}</b>
            </button>
            {rootGroups.map((root) => renderCategoryNode(root))}
          </div>
        </aside>

        <section className="products-list">
          <div className="panel products-section-header products-list-header">
            <div><strong>{selectedGroup?.name ?? t("allProducts")}</strong><span>{total}</span></div>
            <button className="button primary" title={!can("products.create") ? t("noPermission") : ""} disabled={!can("products.create")} onClick={() => { resetForm(); setProductFormOpen((open) => !open); }}>+ {t("create")}</button>
          </div>

          {productFormOpen ? (
            <div className="panel form-grid products-editor">
              <div className="field"><label>SKU</label><input value={sku} onChange={(event) => setSku(event.target.value)} /></div>
              <div className="field"><label>{t("name")}</label><input value={name} onChange={(event) => setName(event.target.value)} /></div>
              <div className="field">
                <label>{t("productCategory")}</label>
                <select value={groupId} onChange={(event) => setGroupId(event.target.value)}>
                  <option value="">{t("notSelected")}</option>
                  {groupOptions.map(({ group, depth }) => <option key={group.id} value={group.id}>{`${"— ".repeat(depth)}${group.name}`}</option>)}
                </select>
              </div>
              <div className="field"><label>{t("basePrice")}</label><input value={basePrice} onChange={(event) => setBasePrice(event.target.value)} /></div>
              <div className="products-form-actions products-editor-actions">
                <button className="button primary" disabled={!can(editingId ? "products.update" : "products.create")} onClick={save}>{editingId ? t("save") : t("create")}</button>
                <button className="button" onClick={() => { resetForm(); setProductFormOpen(false); }}>{t("cancel")}</button>
              </div>
            </div>
          ) : null}

          <div className="panel toolbar" style={{ padding: "8px 10px", marginBottom: 10 }}>
            <input className="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder={t("search")} />
            <select value={sortBy} onChange={(event) => { setSortBy(event.target.value as ProductSort); setPage(0); }}>
              <option value="name">{t("name")}</option>
              <option value="sku">SKU</option>
              <option value="base_price">{t("basePrice")}</option>
              <option value="created_at">ID</option>
              <option value="is_active">{t("active")}</option>
            </select>
            <button className="button" onClick={() => { setSortOrder((current) => current === "asc" ? "desc" : "asc"); setPage(0); }}>
              {sortOrder === "asc" ? "↑" : "↓"}
            </button>
          </div>

          <DataTable<Product>
            rows={rows}
            emptyMessage={t("noProducts")}
            pageSize={PAGE_SIZE}
            columns={[
              { key: "sku", header: "SKU" },
              { key: "name", header: t("name") },
              { key: "group_name", header: t("productCategory"), render: (row) => row.group_name ?? "-" },
              { key: "base_price", header: t("basePrice"), render: (row) => formatMoney(row.base_price) },
              { key: "latest_purchase_cost", header: t("latestPurchaseCost"), render: (row) => row.latest_purchase_cost ? formatMoney(row.latest_purchase_cost) : "-" },
              { key: "markup_percent", header: t("markup"), render: (row) => row.markup_percent !== null && row.markup_percent !== undefined ? `${row.markup_percent}%` : "-" },
              {
                key: "price_review_required",
                header: t("priceControl"),
                render: (row) => row.latest_purchase_cost ? (
                  <span className={row.price_review_required ? "price-control review-required" : "price-control price-ok"}>
                    {t(row.price_review_required ? "priceReviewRequired" : "priceMeetsMarkup")}
                    {row.price_review_required && row.minimum_sale_price ? `: ${formatMoney(row.minimum_sale_price)}` : ""}
                  </span>
                ) : "-"
              },
              { key: "is_active", header: t("active"), render: (row) => row.is_active ? t("yes") : t("no") },
              {
                key: "actions",
                header: t("actions"),
                render: (row) => (
                  <div className="products-row-actions">
                    <button className="button" title={!can("products.update") ? t("noPermission") : ""} disabled={!can("products.update")} onClick={() => edit(row)}>{t("edit")}</button>
                    <button className="button" title={!can("products.delete") ? t("noPermission") : ""} disabled={!can("products.delete")} onClick={() => remove(row)}>{t("delete")}</button>
                  </div>
                )
              }
            ]}
          />
          {pageCount > 1 ? (
            <div className="panel table-footer">
              <span>{page + 1} / {pageCount} · {t("total")}: {total}</span>
              <span>
                <button className="button" disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))}>‹</button>
                <button className="button" disabled={page >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}>›</button>
              </span>
            </div>
          ) : null}
        </section>
      </div>
    </PageScaffold>
  );
}
