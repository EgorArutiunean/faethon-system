import { expect, Page, test } from "@playwright/test";

async function openDocument(page: Page, posted = false) {
  const line = { id: 5, document_id: 42, product_id: 10, product_name: "Товар восстановления", quantity: "2.000", price: "100.00", line_total: "200.00", foreign_price: null, foreign_line_total: null };
  const document = {
    id: 42, number: "RECOVERY-42", document_type: "outgoing", document_date: "2026-10-22", status: posted ? "posted" : "draft",
    partner_id: 1, partner_name: "Клиент", warehouse_id: 1, warehouse_name: "Склад", currency_code: "RUB_PMR", exchange_rate: "1.000000",
    foreign_total_amount: "200.00", total_amount: "200.00", posting_version: posted ? 1 : 0, note: "", updated_at: "2026-10-22T10:00:00", lines: [line],
  };
  const writes: string[] = [];
  await page.addInitScript(() => localStorage.setItem("buy-modern-token", "recovery-token"));
  await page.route("**/api/v1/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: 2, email: "manager@example.com", full_name: "Менеджер", role_names: ["manager"], must_change_password: false,
        permissions: ["documents.read", "documents.update", "documents.post", "documents.create", "products.read", "partners.read", "warehouses.read", "stock.read", "payments.read", "logistics.read"],
      } });
    } else if (path === "/api/v1/documents/42") {
      if (req.method() === "PATCH") {
        writes.push("header");
        Object.assign(document, req.postDataJSON(), { updated_at: `2026-10-22T11:00:${String(writes.length).padStart(2, "0")}` });
      }
      await route.fulfill({ json: document });
    } else if (path === "/api/v1/documents/42/lines/5" && req.method() === "PATCH") {
      writes.push("line");
      const payload = req.postDataJSON();
      Object.assign(line, payload, { quantity: Number(payload.quantity).toFixed(3), price: Number(payload.price).toFixed(2), line_total: (Number(payload.quantity) * Number(payload.price)).toFixed(2) });
      Object.assign(document, { total_amount: line.line_total, foreign_total_amount: line.line_total, updated_at: "2026-10-22T12:00:00" });
      await route.fulfill({ json: line });
    } else if (path.endsWith("/products/options")) {
      await route.fulfill({ json: [{ id: 10, sku: "RECOVERY", name: line.product_name, base_price: "100.00", is_active: true }] });
    } else if (path.endsWith("/warehouses")) {
      await route.fulfill({ json: [{ id: 1, name: "Склад" }] });
    } else if (path.endsWith("/partners/options") || path.endsWith("/partners/1")) {
      const partner = { id: 1, name: "Клиент", partner_type: "both", is_active: true };
      await route.fulfill({ json: path.endsWith("/partners/1") ? partner : [partner] });
    } else if (path.endsWith("/currencies")) {
      await route.fulfill({ json: [{ id: 1, code: "RUB_PMR", name: "Рубль ПМР", is_base: true, is_active: true }] });
    } else if (path.endsWith("/payments/document-summary/42")) {
      await route.fulfill({ json: { document_id: 42, document_number: document.number, document_type: "outgoing", document_status: document.status,
        partner_id: 1, partner_name: "Клиент", total_amount: document.total_amount, paid_amount: "0.00", outstanding_amount: document.total_amount,
        payment_type: "customer_payment", payments_count: 0, payments: [],
      } });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  await page.goto("/documents/42");
  await expect(page.getByRole("heading", { name: /RECOVERY-42/ })).toBeVisible();
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("");
  return { document, writes };
}

async function reloadWithInput(page: Page) {
  page.once("dialog", (dialog) => dialog.accept());
  await page.reload();
}

test("RECOVERY-DOC-01: реквизиты и строка восстанавливаются после обновления без записи на сервер", async ({ page }) => {
  const data = await openDocument(page);
  await page.getByTestId("document-line-edit-5").click();
  await page.getByTestId("document-line-quantity").fill("3");
  await page.getByTestId("document-line-price").fill("120");
  await page.getByLabel("Примечание", { exact: true }).fill("Продолжить после перерыва");
  await reloadWithInput(page);
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("Продолжить после перерыва");
  await expect(page.getByTestId("document-line-quantity")).toHaveValue("3");
  await expect(page.getByTestId("document-line-price")).toHaveValue("120");
  await expect(page.getByTestId("document-line-editing")).toBeVisible();
  expect(data.writes).toEqual([]);
  await page.getByRole("button", { name: "Сохранить строку", exact: true }).click();
  await expect(page.getByTestId("document-line-editing")).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("Продолжить после перерыва");
  expect(data.document.lines[0].quantity).toBe("3.000");
  expect(data.document.total_amount).toBe("360.00");
});

test("RECOVERY-DOC-02: восстановленный ввод можно сбросить к сохранённому документу", async ({ page }) => {
  const data = await openDocument(page);
  await page.getByLabel("Примечание", { exact: true }).fill("Не сохранять");
  await reloadWithInput(page);
  await page.getByRole("button", { name: "Сбросить восстановленный ввод", exact: true }).click();
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("");
  await page.reload();
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toHaveCount(0);
  expect(data.writes).toEqual([]);
});

test("RECOVERY-DOC-03: ввод прежней версии не подменяет изменившийся документ", async ({ page }) => {
  const data = await openDocument(page);
  await page.getByLabel("Примечание", { exact: true }).fill("Старая правка");
  data.document.note = "Обновлено другим сотрудником";
  data.document.updated_at = "2026-10-22T13:00:00";
  await reloadWithInput(page);
  await expect(page.getByText(/Сохранённый ввод относится к прежней версии/)).toBeVisible();
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("Обновлено другим сотрудником");
  await page.getByLabel("Примечание", { exact: true }).fill("Новая правка");
  await page.getByRole("button", { name: "Удалить сохранённый ввод", exact: true }).click();
  await expect(page.getByLabel("Примечание", { exact: true })).toHaveValue("Новая правка");
  expect(data.writes).toEqual([]);
});

test("RECOVERY-DOC-04: исправление проведённого документа восстанавливается без перепроведения", async ({ page }) => {
  const data = await openDocument(page, true);
  await page.getByTestId("document-correction-start").click();
  await page.getByTestId("document-correction-reason").fill("Уточнение количества");
  await page.getByTestId("document-line-edit-5").click();
  await page.getByTestId("document-line-quantity").fill("4");
  await page.getByRole("button", { name: "Сохранить строку", exact: true }).click();
  await reloadWithInput(page);
  await expect(page.getByText("Восстановлены несохранённые данные", { exact: true })).toBeVisible();
  await expect(page.getByTestId("document-correction-reason")).toHaveValue("Уточнение количества");
  await expect(page.getByRole("row").filter({ hasText: "Товар восстановления" })).toContainText("4.000");
  expect(data.writes).toEqual([]);
  expect(data.document.status).toBe("posted");
  expect(data.document.lines[0].quantity).toBe("2.000");
});
