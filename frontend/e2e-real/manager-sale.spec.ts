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

async function loginToken(api: APIRequestContext, email: string, password: string) {
  const response = await api.post("auth/login", { data: { email, password } });
  if (!response.ok()) {
    throw new Error(`auth/login: ${response.status()} ${await response.text()}`);
  }
  return (await response.json()).access_token as string;
}

async function prepareStock(): Promise<SeededSaleData> {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");

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

async function createDraftThroughUi(
  page: Page,
  documentType: "incoming" | "outgoing" | "transfer",
  warehouseId: number,
  partnerId?: number,
  destinationWarehouseId?: number,
) {
  await page.goto("/documents", { waitUntil: "domcontentloaded" });
  await page.getByTestId("draft-document-type").selectOption(documentType);
  await page.getByTestId("draft-document-warehouse").selectOption(String(warehouseId));
  if (destinationWarehouseId) {
    await page.getByTestId("draft-document-destination").selectOption(String(destinationWarehouseId));
  }
  if (partnerId) {
    await page.getByTestId("draft-document-partner").selectOption(String(partnerId));
  }
  await page.getByTestId("draft-document-create").click();
  await expect(page).toHaveURL(/\/documents\/\d+$/);
  const documentId = Number(page.url().match(/\/documents\/(\d+)$/)?.[1]);
  expect(documentId).toBeGreaterThan(0);
  return documentId;
}

test("M03: продажа через интерфейс согласует документ, склад, долг и отчет", async ({ page }) => {
  const seeded = await prepareStock();
  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "outgoing", seeded.warehouseId, seeded.customerId);
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

test("M02: валютный приход фиксирует курс, суммы и остаток в PostgreSQL", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const managerToken = await loginToken(api, "manager@example.com", "manager123");
  const adminToken = await loginToken(api, "admin@example.com", "admin123");
  const today = new Date().toISOString().slice(0, 10);

  const warehouse = await postJson(api, "/warehouses", managerToken, {
    code: "E2E-FX-WAREHOUSE",
    name: "E2E FX Warehouse",
  });
  const product = await postJson(api, "/products", managerToken, {
    sku: "E2E-FX-PRODUCT",
    name: "E2E FX Product",
    base_price: "100.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", managerToken, {
    code: "E2E-FX-SUPPLIER",
    name: "E2E FX Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  await postJson(api, "/currencies/rates", adminToken, {
    currency_code: "USD",
    rate_date: today,
    rate_to_base: "16.200000",
    note: "M02",
  });

  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "incoming", warehouse.id, supplier.id);
  await page.getByTestId("document-currency").selectOption("USD");
  await expect.poll(async () => Number(await page.getByTestId("document-exchange-rate").inputValue())).toBe(16.2);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("10");
  await expect(page.getByText("\u041f\u0435\u0440\u0435\u0441\u043c\u043e\u0442\u0440\u0438\u0442\u0435 \u0446\u0435\u043d\u0443 \u0440\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u0438.")).toBeVisible();
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E FX Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041f\u0440\u043e\u0432\u0435\u0434\u0451\u043d", { exact: true })).toBeVisible();

  const [documentResponse, stockResponse] = await Promise.all([
    api.get(`documents/${documentId}`, { headers: { Authorization: `Bearer ${managerToken}` } }),
    api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, {
      headers: { Authorization: `Bearer ${managerToken}` },
    }),
  ]);
  expect(documentResponse.ok()).toBeTruthy();
  expect(stockResponse.ok()).toBeTruthy();
  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  expect(document.status).toBe("posted");
  expect(document.currency_code).toBe("USD");
  expect(document.exchange_rate).toBe("16.200000");
  expect(document.foreign_total_amount).toBe("20.00");
  expect(document.total_amount).toBe("324.00");
  expect(stock[0].quantity).toBe("2.000");
  await api.dispose();
});

test("M04: неуспешный расход не меняет остаток и долг", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");
  const warehouse = await postJson(api, "/warehouses", token, {
    code: "E2E-EMPTY-WAREHOUSE",
    name: "E2E Empty Warehouse",
  });
  const product = await postJson(api, "/products", token, {
    sku: "E2E-EMPTY-PRODUCT",
    name: "E2E Empty Product",
    base_price: "100.00",
    is_active: true,
  });
  const customer = await postJson(api, "/partners", token, {
    code: "E2E-EMPTY-CUSTOMER",
    name: "E2E Empty Customer",
    partner_type: "customer",
    is_active: true,
  });

  await loginAsManager(page);
  const documentId = await createDraftThroughUi(page, "outgoing", warehouse.id, customer.id);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("1");
  await page.getByTestId("document-line-price").fill("100");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Empty Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043e\u0441\u0442\u0430\u0442\u043a\u0430", { exact: true }).first()).toBeVisible();

  const headers = { Authorization: `Bearer ${token}` };
  const [documentResponse, stockResponse, debtResponse, registerResponse] = await Promise.all([
    api.get(`documents/${documentId}`, { headers }),
    api.get(`stock/balances?warehouse_id=${warehouse.id}&product_id=${product.id}`, { headers }),
    api.get(`partners/${customer.id}/balance`, { headers }),
    api.get(`reports/documents-register?partner_id=${customer.id}&status=posted`, { headers }),
  ]);
  const document = await documentResponse.json();
  const stock = await stockResponse.json();
  const debt = await debtResponse.json();
  const register = await registerResponse.json();
  expect(document.status).toBe("draft");
  expect(stock).toEqual([]);
  expect(debt.balance).toBe("0");
  expect(register.rows).toEqual([]);
  expect(register.total_amount).toBe("0");
  await api.dispose();
});

test("M05: перемещение сохраняет общий остаток и создает два движения", async ({ page }) => {
  const api = await request.newContext({ baseURL: apiBaseUrl });
  const token = await loginToken(api, "manager@example.com", "manager123");
  const source = await postJson(api, "/warehouses", token, {
    code: "E2E-TRANSFER-SOURCE",
    name: "E2E Transfer Source",
  });
  const destination = await postJson(api, "/warehouses", token, {
    code: "E2E-TRANSFER-DESTINATION",
    name: "E2E Transfer Destination",
  });
  const product = await postJson(api, "/products", token, {
    sku: "E2E-TRANSFER-PRODUCT",
    name: "E2E Transfer Product",
    base_price: "50.00",
    is_active: true,
  });
  const supplier = await postJson(api, "/partners", token, {
    code: "E2E-TRANSFER-SUPPLIER",
    name: "E2E Transfer Supplier",
    partner_type: "supplier",
    is_active: true,
  });
  const incoming = await postJson(api, "/documents", token, {
    document_type: "incoming",
    document_date: "2026-07-24",
    partner_id: supplier.id,
    warehouse_id: source.id,
  });
  await postJson(api, `/documents/${incoming.id}/lines`, token, {
    product_id: product.id,
    quantity: "5",
    price: "40.00",
  });
  await postJson(api, `/documents/${incoming.id}/post`, token, {});

  await loginAsManager(page);
  const transferId = await createDraftThroughUi(page, "transfer", source.id, undefined, destination.id);
  await page.getByTestId("document-product").selectOption(String(product.id));
  await page.getByTestId("document-line-quantity").fill("2");
  await page.getByTestId("document-line-price").fill("50");
  await page.getByTestId("document-line-add").click();
  await expect(page.getByRole("cell", { name: "E2E Transfer Product" })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByTestId("document-post").click();
  await expect(page.getByText("\u041f\u0440\u043e\u0432\u0435\u0434\u0451\u043d", { exact: true })).toBeVisible();

  const headers = { Authorization: `Bearer ${token}` };
  const [sourceResponse, destinationResponse, movementsResponse, reportResponse] = await Promise.all([
    api.get(`stock/balances?warehouse_id=${source.id}&product_id=${product.id}`, { headers }),
    api.get(`stock/balances?warehouse_id=${destination.id}&product_id=${product.id}`, { headers }),
    api.get(`stock/movements?document_id=${transferId}`, { headers }),
    api.get(`reports/stock-balances?product_id=${product.id}`, { headers }),
  ]);
  const sourceStock = await sourceResponse.json();
  const destinationStock = await destinationResponse.json();
  const movements = await movementsResponse.json();
  const report = await reportResponse.json();
  expect(sourceStock[0].quantity).toBe("3.000");
  expect(destinationStock[0].quantity).toBe("2.000");
  expect(movements).toHaveLength(2);
  expect(movements.map((row: { quantity_delta: string }) => row.quantity_delta).sort()).toEqual(["-2.000", "2.000"]);
  expect(report.total_quantity).toBe("5.000");
  await api.dispose();
});
