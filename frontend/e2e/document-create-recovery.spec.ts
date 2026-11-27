import { expect, type Page, test } from "@playwright/test";

async function mockCreate(page: Page, options: { beforeCreate?: () => Promise<void>; failFirst?: boolean } = {}) {
  const posts: unknown[] = [];
  await page.addInitScript(() => localStorage.setItem("buy-modern-token", "create-test"));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/me")) {
      await route.fulfill({ json: { id: 2, email: "manager@example.com", full_name: "Менеджер", role_names: ["manager"], must_change_password: false, permissions: ["documents.read", "documents.create", "documents.update", "warehouses.read", "partners.read"] } });
    } else if (path === "/api/v1/documents" && request.method() === "POST") {
      posts.push(request.postDataJSON());
      await options.beforeCreate?.();
      if (options.failFirst && posts.length === 1) {
        await route.fulfill({ status: 503, json: { detail: "Сохранение временно недоступно" } });
        return;
      }
      await route.fulfill({ json: { ...request.postDataJSON(), id: 42, total_amount: "0", currency_code: "RUB_PMR", exchange_rate: "1", foreign_total_amount: "0", posting_version: 0, lines: [] } });
    } else if (path === "/api/v1/documents/42") {
      await route.fulfill({ json: { id: 42, document_type: "incoming", document_date: "2026-10-22", status: "draft", warehouse_id: 1, partner_id: 1, total_amount: "0", currency_code: "RUB_PMR", exchange_rate: "1", foreign_total_amount: "0", posting_version: 0, lines: [] } });
    } else if (path.endsWith("/documents/page")) {
      await route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 25 } });
    } else if (path.endsWith("/warehouses")) {
      await route.fulfill({ json: [{ id: 1, name: "Склад" }, { id: 2, name: "Другой склад" }] });
    } else if (path.endsWith("/partners/options")) {
      await route.fulfill({ json: [{ id: 1, name: "Поставщик", partner_type: "both", is_active: true }] });
    } else if (path.endsWith("/partners/1")) {
      await route.fulfill({ json: { id: 1, name: "Поставщик", partner_type: "both", is_active: true } });
    } else {
      await route.fulfill({ json: [] });
    }
  });
  return posts;
}

test("новый документ восстанавливает реквизиты после reload без автоматического создания", async ({ page }) => {
  const posts = await mockCreate(page);
  await page.goto("/documents");
  await page.getByRole("button", { name: "Создать документ", exact: true }).first().click();
  await page.getByTestId("draft-document-number").fill("RECOVER-CREATE");
  await page.getByTestId("draft-document-date").fill("2026-10-23");
  await page.getByTestId("draft-document-warehouse").selectOption("2");
  await page.getByTestId("draft-document-partner-search").fill("Поставщик");
  await page.getByTestId("draft-document-partner").selectOption("1");
  await page.reload();
  await expect(page.getByTestId("draft-document-number")).toHaveValue("RECOVER-CREATE");
  await expect(page.getByTestId("draft-document-date")).toHaveValue("2026-10-23");
  await expect(page.getByTestId("draft-document-warehouse")).toHaveValue("2");
  await expect(page.getByTestId("draft-document-partner")).toHaveValue("1");
  await expect(page.getByTestId("draft-document-partner-search")).toHaveValue("Поставщик");
  expect(posts).toHaveLength(0);
});

test("успешное создание удаляет сохранённый ввод, закрытие тоже очищает форму", async ({ page }) => {
  const posts = await mockCreate(page);
  await page.goto("/documents?create=incoming");
  await page.getByTestId("draft-document-number").fill("CLEARED-CREATE");
  await page.getByTestId("draft-document-warehouse").selectOption("1");
  await page.getByTestId("draft-document-partner").selectOption("1");
  await page.getByTestId("draft-document-create").click();
  await expect(page).toHaveURL(/\/documents\/42$/);
  expect(posts).toHaveLength(1);
  expect(await page.evaluate(() => localStorage.getItem("buy-modern-input:2:document-create:incoming"))).toBeNull();
  await page.goto("/documents?create=incoming");
  await expect(page.getByTestId("draft-document-number")).toHaveValue("");
  await page.getByTestId("draft-document-number").fill("CANCELLED-CREATE");
  await page.getByRole("button", { name: "Закрыть", exact: true }).click();
  await page.reload();
  await expect(page.getByTestId("draft-document-number")).toHaveValue("");
});

test("быстрая новая продажа не восстанавливает реквизиты общего прихода", async ({ page }) => {
  const posts = await mockCreate(page);
  await page.goto("/documents");
  await page.getByRole("button", { name: "Создать документ", exact: true }).first().click();
  await page.getByTestId("draft-document-number").fill("GENERAL-INCOMING");
  await page.goto("/documents?create=outgoing");
  await expect(page.getByTestId("draft-document-type")).toHaveValue("outgoing");
  await expect(page.getByTestId("draft-document-number")).toHaveValue("");
  await page.getByTestId("draft-document-number").fill("QUICK-SALE");
  await page.reload();
  await expect(page.getByTestId("draft-document-type")).toHaveValue("outgoing");
  await expect(page.getByTestId("draft-document-number")).toHaveValue("QUICK-SALE");
  await page.goto("/documents");
  await expect(page.getByTestId("draft-document-type")).toHaveValue("incoming");
  await expect(page.getByTestId("draft-document-number")).toHaveValue("GENERAL-INCOMING");
  expect(posts).toHaveLength(0);
});

test("явная смена типа в быстром создании сохраняется вместе с введёнными реквизитами", async ({ page }) => {
  const posts = await mockCreate(page);
  await page.goto("/documents?create=outgoing");
  await page.getByTestId("draft-document-number").fill("SWITCHED-TYPE");
  await page.getByTestId("draft-document-type").selectOption("incoming");
  await page.getByTestId("draft-document-warehouse").selectOption("2");
  await page.getByTestId("draft-document-partner").selectOption("1");
  await page.reload();
  await expect(page.getByTestId("draft-document-type")).toHaveValue("incoming");
  await expect(page.getByTestId("draft-document-number")).toHaveValue("SWITCHED-TYPE");
  await expect(page.getByTestId("draft-document-warehouse")).toHaveValue("2");
  await expect(page.getByTestId("draft-document-partner")).toHaveValue("1");
  expect(posts).toHaveLength(0);
});

test("медленное создание отправляется один раз, после ошибки можно повторить без потери ввода", async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  const posts = await mockCreate(page, { beforeCreate: () => pending, failFirst: true });
  await page.goto("/documents?create=incoming");
  await page.getByTestId("draft-document-number").fill("SINGLE-CREATE");
  await page.getByTestId("draft-document-warehouse").selectOption("1");
  await page.getByTestId("draft-document-partner").selectOption("1");
  await page.getByTestId("draft-document-create").evaluate((button: HTMLButtonElement) => { button.click(); button.click(); });
  await expect.poll(() => posts.length).toBe(1);
  await expect(page.getByTestId("draft-document-create")).toBeDisabled();
  await expect(page.getByTestId("draft-document-type")).toBeDisabled();
  await expect(page.getByRole("button", { name: "Закрыть", exact: true })).toBeDisabled();
  release();
  await expect(page.locator(".error-panel").first()).toContainText("Сохранение временно недоступно");
  await expect(page.getByTestId("draft-document-create")).toBeEnabled();
  await expect(page.getByTestId("draft-document-number")).toHaveValue("SINGLE-CREATE");
  await page.getByTestId("draft-document-create").click();
  await expect(page).toHaveURL(/\/documents\/42$/);
  expect(posts).toHaveLength(2);
});
