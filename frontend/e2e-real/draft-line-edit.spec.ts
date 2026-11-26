import { expect, request, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:18000/api/v1/";

test("DRAFT-EDIT: замена строки валютного черновика сохраняет ID и проводит только новые суммы в PostgreSQL", async ({ page }) => {
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
    const warehouse = await create("warehouses", { code: "E2E-DRAFT-EDIT-WH", name: "E2E Склад редактирования черновика" });
    const supplier = await create("partners", { code: "E2E-DRAFT-EDIT-SUP", name: "E2E Поставщик редактирования", partner_type: "supplier", is_active: true });
    const original = await create("products", { sku: "E2E-DRAFT-EDIT-ORIGINAL", name: "E2E Исходный товар черновика", base_price: "200", is_active: true });
    const replacement = await create("products", { sku: "E2E-DRAFT-EDIT-REPLACEMENT", name: "E2E Заменённый товар черновика", base_price: "250", is_active: true });
    const draft = await create("documents", {
      document_type: "incoming", document_date: "2026-10-22", warehouse_id: warehouse.id, partner_id: supplier.id,
      currency_code: "USD", exchange_rate: "16.200000",
    });
    const line = await create(`documents/${draft.id}/lines`, { product_id: original.id, quantity: "2", foreign_price: "10" });

    await page.goto("/login");
    await page.getByLabel("Email").fill("manager@example.com");
    await page.getByLabel("Пароль").fill("manager123");
    await page.getByRole("button", { name: "Войти" }).click();
    await expect(page.getByTestId("header-user")).toBeVisible();
    await page.goto(`/documents/${draft.id}`);
    await page.getByTestId(`document-line-edit-${line.id}`).click();
    await expect(page.getByTestId("document-line-price")).toHaveValue("10.00");
    const picker = page.getByTestId("document-product");
    await picker.fill(replacement.sku);
    await page.getByRole("option", { name: new RegExp(replacement.sku) }).click();
    await page.getByTestId("document-line-quantity").fill("3");
    await page.getByTestId("document-line-price").fill("11");
    await page.getByRole("button", { name: "Сохранить строку", exact: true }).click();
    await expect(page.getByTestId("document-line-editing")).toHaveCount(0);

    const edited = await read(`documents/${draft.id}`);
    expect(edited.status).toBe("draft");
    expect(edited.lines).toHaveLength(1);
    expect(edited.lines[0]).toMatchObject({
      id: line.id, product_id: replacement.id, quantity: "3.000", price: "178.20", foreign_price: "11.00", line_total: "534.60",
    });
    expect(edited.total_amount).toBe("534.60");
    expect(edited.foreign_total_amount).toBe("33.00");
    expect(await read(`stock/movements?document_id=${draft.id}`)).toHaveLength(0);
    expect(Number((await read(`partners/${supplier.id}/balance`)).balance)).toBe(0);

    await page.getByTestId("document-post").click();
    await page.getByRole("dialog", { name: "Подтверждение действия" }).getByRole("button", { name: "Провести", exact: true }).click();
    await expect(page.getByText("Проведён", { exact: true })).toBeVisible();
    const posted = await read(`documents/${draft.id}`);
    expect(posted.lines[0].id).toBe(line.id);
    expect(posted.total_amount).toBe("534.60");
    const stock = await read(`stock/balances?warehouse_id=${warehouse.id}`);
    expect(stock.find((row: { product_id: number }) => row.product_id === replacement.id)?.quantity).toBe("3.000");
    expect(stock.find((row: { product_id: number }) => row.product_id === original.id)).toBeUndefined();
    expect(Number((await read(`partners/${supplier.id}/balance`)).balance)).toBe(-534.6);
    const movements = await read(`stock/movements?document_id=${draft.id}`);
    expect(movements).toHaveLength(1);
    expect(movements[0]).toMatchObject({ product_id: replacement.id, quantity_delta: "3.000" });
    const denied = await api.patch(`documents/${draft.id}/lines/${line.id}`, { headers, data: { quantity: "4" } });
    expect(denied.status()).toBe(409);
  } finally {
    await api.dispose();
  }
});
