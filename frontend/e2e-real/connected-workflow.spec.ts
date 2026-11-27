import { APIRequestContext, expect, Page, request, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:18000/api/v1/";

async function post(api: APIRequestContext, path: string, token: string, data: Record<string, unknown>) {
  const response = await api.post(path, { headers: { Authorization: `Bearer ${token}` }, data });
  expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function get(api: APIRequestContext, path: string, token: string) {
  const response = await api.get(path, { headers: { Authorization: `Bearer ${token}` } });
  expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
}

async function confirm(page: Page) {
  const prompt = page.getByRole("dialog", { name: "Подтверждение действия" });
  await expect(prompt).toBeVisible();
  await prompt.getByRole("button").last().click();
}

test("CONNECTED-PG: карточка → частичная оплата с восстановлением → складское задание сохраняют учётные связи", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  try {
    const auth = await api.post("auth/login", { data: { email: "manager@example.com", password: "manager123" } });
    expect(auth.ok()).toBeTruthy();
    const token = (await auth.json()).access_token as string;
    const warehouse = await post(api, "warehouses", token, { code: "E2E-CONNECTED-W", name: "E2E Склад связанных операций" });
    const product = await post(api, "products", token, { sku: "E2E-CONNECTED-P", name: "E2E Товар связанных операций", base_price: "100.00", is_active: true });
    const supplier = await post(api, "partners", token, { code: "E2E-CONNECTED-S", name: "E2E Поставщик связанных операций", partner_type: "supplier", is_active: true });
    const customer = await post(api, "partners", token, { code: "E2E-CONNECTED-C", name: "E2E Покупатель связанных операций", partner_type: "customer", is_active: true });
    const incoming = await post(api, "documents", token, { document_type: "incoming", document_date: "2026-10-22", warehouse_id: warehouse.id, partner_id: supplier.id });
    await post(api, `documents/${incoming.id}/lines`, token, { product_id: product.id, quantity: "5", price: "80.00" });
    await post(api, `documents/${incoming.id}/post`, token, {});
    const sale = await post(api, "documents", token, { document_type: "outgoing", document_date: "2026-10-22", warehouse_id: warehouse.id, partner_id: customer.id });
    await post(api, `documents/${sale.id}/lines`, token, { product_id: product.id, quantity: "2", price: "100.00" });
    await post(api, `documents/${sale.id}/post`, token, {});
    const firstPayment = await post(api, "payments", token, { partner_id: customer.id, payment_date: "2026-10-22", payment_type: "customer_payment", amount: "40.00", method: "cash", allocations: [{ document_id: sale.id, amount: "40.00" }] });
    await post(api, `payments/${firstPayment.id}/post`, token, {});
    const cashBefore = Number((await get(api, "cash/balance", token)).balance);

    await page.goto("/login");
    await page.getByLabel("Email").fill("manager@example.com");
    await page.getByLabel("Пароль").fill("manager123");
    await page.getByRole("button", { name: "Войти", exact: true }).click();
    await expect(page.getByTestId("header-user")).toBeVisible();
    await page.goto(`/documents/${sale.id}`);
    await expect(page.getByTestId("document-paid")).toHaveText(/40[,.]00/);
    await expect(page.getByTestId("document-outstanding")).toHaveText(/160[,.]00/);
    await page.getByRole("link", { name: "Принять оплату", exact: true }).click();
    await expect(page.getByTestId("payment-partner")).toHaveValue(String(customer.id));
    await expect(page.getByTestId("payment-amount")).toHaveValue("160.00");
    await page.getByTestId("payment-amount").fill("60");
    await page.reload();
    await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toBeVisible();
    await expect(page.getByTestId("payment-amount")).toHaveValue("60");
    await expect(page.getByTestId(`payment-allocation-${sale.id}`)).toHaveValue("60.00");
    expect((await get(api, `payments/page?document_id=${sale.id}`, token)).total).toBe(1);
    const saveResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/payments" && response.request().method() === "POST");
    await page.getByTestId("payment-save").click();
    const saved = await (await saveResponse).json();
    expect(saved.status).toBe("draft");
    expect(saved.allocations).toMatchObject([{ document_id: sale.id, amount: "60.00" }]);
    await page.getByTestId(`payment-post-${saved.id}`).click();
    await confirm(page);
    await expect(page.getByTestId(`payment-post-${saved.id}`)).toHaveCount(0);
    const summary = await get(api, `payments/document-summary/${sale.id}`, token);
    expect(summary.paid_amount).toBe("100.00");
    expect(summary.outstanding_amount).toBe("100.00");
    expect((await get(api, `partners/${customer.id}/balance`, token)).balance).toBe("100.00");
    expect(Number((await get(api, "cash/balance", token)).balance)).toBeCloseTo(cashBefore + 60, 2);

    const tasks = await get(api, `logistics/tasks?document_id=${sale.id}`, token);
    expect(tasks).toHaveLength(1);
    await page.goto(`/documents/${sale.id}`);
    await page.getByRole("link", { name: `Открыть задание #${tasks[0].id}`, exact: true }).click();
    await expect(page.getByRole("heading", { name: sale.number, exact: true })).toBeVisible();
    await page.getByTestId("start-warehouse-task").click();
    await expect(page.getByTestId("confirm-warehouse-task")).toBeVisible();
    await page.getByTestId("confirm-warehouse-task").click();
    await expect(page.getByTestId("confirm-warehouse-task")).toHaveCount(0);
    expect((await get(api, `logistics/tasks/${tasks[0].id}`, token)).status).toBe("completed");
    const stock = await get(api, `stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, token);
    expect(stock[0].quantity).toBe("3.000");
  } finally {
    await api.dispose();
  }
});
