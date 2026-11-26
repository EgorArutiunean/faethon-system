import { expect, request, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:18000/api/v1/";

test("COPY: копия проведённого валютного документа создаёт независимый черновик без движений в PostgreSQL", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  try {
    const login = await api.post("auth/login", { data: { email: "manager@example.com", password: "manager123" } });
    expect(login.ok()).toBeTruthy();
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
    async function create(path: string, data: Record<string, unknown>) {
      const response = await api.post(path, { headers, data });
      expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
      return response.json();
    }
    async function read(path: string) {
      const response = await api.get(path, { headers });
      expect(response.ok(), path).toBeTruthy();
      return response.json();
    }
    const warehouse = await create("warehouses", { code: "E2E-COPY-WH", name: "E2E Склад копирования документа" });
    const supplier = await create("partners", { code: "E2E-COPY-SUP", name: "E2E Поставщик копирования", partner_type: "supplier", is_active: true });
    const product = await create("products", { sku: "E2E-COPY-PRODUCT", name: "E2E Товар для копирования", base_price: "250", is_active: true });
    const source = await create("documents", {
      document_type: "incoming", document_date: "2026-10-22", warehouse_id: warehouse.id, partner_id: supplier.id,
      currency_code: "USD", exchange_rate: "16.200000", note: "Copy source note",
    });
    const sourceLine = await create(`documents/${source.id}/lines`, { product_id: product.id, quantity: "2", foreign_price: "10" });
    await create(`documents/${source.id}/post`, {});
    const before = await read(`documents/${source.id}`);
    const sourceTasks = await read(`logistics/tasks?document_id=${source.id}`);
    const stockBefore = await read(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`);
    const balanceBefore = await read(`partners/${supplier.id}/balance`);

    await page.goto("/login");
    await page.getByLabel("Email").fill("manager@example.com");
    await page.getByLabel("Пароль").fill("manager123");
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.getByTestId("header-user")).toBeVisible();
    await page.goto(`/documents/${source.id}`);
    await page.locator(".document-more-actions > summary").click();
    await page.getByTestId("document-copy").click();
    const copyDialog = page.getByRole("dialog", { name: /Копировать документ/ });
    await expect(copyDialog).toBeVisible();
    await copyDialog.getByTestId("document-copy-date").fill("2026-10-23");
    await copyDialog.getByTestId("document-copy-submit").click();
    await expect(page).toHaveURL(new RegExp(`/documents/(?!${source.id}$)\\d+$`));
    const copyId = Number(page.url().match(/\/documents\/(\d+)$/)?.[1]);
    expect(copyId).toBeGreaterThan(0);

    const copied = await read(`documents/${copyId}`);
    expect(copied.status).toBe("draft");
    expect(copied.posting_version).toBe(0);
    expect(copied.number).not.toBe(before.number);
    expect(copied.document_date).toBe("2026-10-23");
    expect(copied).toMatchObject({ warehouse_id: warehouse.id, partner_id: supplier.id, note: "Copy source note", currency_code: "USD", exchange_rate: "16.200000", total_amount: "324.00", foreign_total_amount: "20.00" });
    expect(copied.lines).toHaveLength(1);
    expect(copied.lines[0].id).not.toBe(sourceLine.id);
    expect(copied.lines[0]).toMatchObject({ product_id: product.id, quantity: "2.000", price: "162.00", foreign_price: "10.00" });
    expect(await read(`stock/movements?document_id=${copyId}`)).toHaveLength(0);
    expect(await read(`logistics/tasks?document_id=${copyId}`)).toHaveLength(0);
    expect(await read(`documents/${copyId}/revisions`)).toHaveLength(0);
    expect(await read(`documents/${source.id}`)).toEqual(before);
    expect(await read(`logistics/tasks?document_id=${source.id}`)).toEqual(sourceTasks);
    expect(await read(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`)).toEqual(stockBefore);
    expect(await read(`partners/${supplier.id}/balance`)).toEqual(balanceBefore);
    await expect(page.getByTestId(`document-line-edit-${copied.lines[0].id}`)).toBeEnabled();
  } finally {
    await api.dispose();
  }
});
