import { APIRequestContext, expect, Page, request, test } from "@playwright/test";

const apiBaseUrl = "http://127.0.0.1:18000/api/v1/";

function relativeApiPath(path: string) {
  return path.replace(/^\//, "");
}

type SeededSaleData = {
  token: string;
  productId: number;
  warehouseId: number;
  customerId: number;
};

async function postJson(api: APIRequestContext, path: string, token: string, data: Record<string, unknown>) {
  const response = await api.post(relativeApiPath(path), {
    headers: { Authorization: `Bearer ${token}` },
    data,
  });
  if (!response.ok()) {
    throw new Error(`${path}: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

async function prepareStock(): Promise<SeededSaleData> {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const login = await api.post("auth/login", {
    data: { email: "manager@example.com", password: "manager123" },
  });
  expect(login.ok()).toBeTruthy();
  const token = (await login.json()).access_token as string;

  const warehouse = await postJson(api, "/warehouses", token, {
    code: "E2E-MAIN",
    name: "E2E Основной склад",
    address: "Тестовый адрес",
  });
  const product = await postJson(api, "/products", token, {
    sku: "E2E-PRODUCT",
    name: "E2E Контрольный товар",
    base_price: "150.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", token, {
    code: "E2E-SUPPLIER",
    name: "E2E Поставщик",
    partner_type: "supplier",
    is_active: true,
  });
  const customer = await postJson(api, "/partners", token, {
    code: "E2E-CUSTOMER",
    name: "E2E Клиент",
    partner_type: "customer",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", token, {
    document_type: "incoming",
    document_date: "2026-07-24",
    status: "draft",
    partner_id: supplier.id,
    warehouse_id: warehouse.id,
    total_amount: "0",
  });
  await postJson(api, `/documents/${incoming.id}/lines`, token, {
    product_id: product.id,
    quantity: "5",
    price: "80.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, token, {});

  const initialStock = await api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(initialStock.ok()).toBeTruthy();
  expect((await initialStock.json())[0].quantity).toBe("5.000");
  await api.dispose();

  return {
    token,
    productId: product.id,
    warehouseId: warehouse.id,
    customerId: customer.id,
  };
}

async function loginAsManager(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("Email").fill("manager@example.com");
  await page.getByLabel("Пароль").fill("manager123");
  await page.getByRole("button", { name: "Войти" }).click();
  await expect(page.getByText("Роль: Менеджер")).toBeVisible();
}

test("M03: продажа через интерфейс согласует документ, склад, долг и отчет", async ({ page }) => {
  const seeded = await prepareStock();
  await loginAsManager(page);
  await page.goto("/documents", { waitUntil: "domcontentloaded" });

  await page.getByTestId("draft-document-type").selectOption("outgoing");
  await page.getByTestId("draft-document-warehouse").selectOption(String(seeded.warehouseId));
  await page.getByTestId("draft-document-partner").selectOption(String(seeded.customerId));
  await page.getByTestId("draft-document-create").click();
  await expect(page).toHaveURL(/\/documents\/\d+$/);

  const documentId = Number(page.url().match(/\/documents\/(\d+)$/)?.[1]);
  expect(documentId).toBeGreaterThan(0);
  await page.getByTestId("document-product").selectOption(String(seeded.productId));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("150");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Контрольный товар" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("Проведён", { exact: true })).toBeVisible();
  await expect(page.getByTestId("document-post")).toBeDisabled();

  const api = await request.newContext({
    baseURL: apiBaseUrl,
    extraHTTPHeaders: { Authorization: `Bearer ${seeded.token}` },
  });
  const [documentResponse, stockResponse, debtResponse, registerResponse] = await Promise.all([
    api.get(`documents/${documentId}`),
    api.get(`stock/balances?warehouse_id=${seeded.warehouseId}&product_id=${seeded.productId}`),
    api.get(`partners/${seeded.customerId}/balance`),
    api.get(`reports/documents-register?partner_id=${seeded.customerId}&status=posted`),
  ]);

  expect(documentResponse.ok()).toBeTruthy();
  expect(stockResponse.ok()).toBeTruthy();
  expect(debtResponse.ok()).toBeTruthy();
  expect(registerResponse.ok()).toBeTruthy();

  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const debt = await debtResponse.json();
  const register = await registerResponse.json();
  expect(document.status).toBe("posted");
  expect(document.total_amount).toBe("300.00");
  expect(stock[0].quantity).toBe("3.000");
  expect(debt.balance).toBe("300.00");
  expect(register.total_amount).toBe("300.00");
  expect(register.rows).toEqual(expect.arrayContaining([expect.objectContaining({ id: documentId, total_amount: "300.00" })]));
  await api.dispose();
});
