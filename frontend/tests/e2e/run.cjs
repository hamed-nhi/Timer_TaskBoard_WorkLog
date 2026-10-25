/* Real Chrome tests against the isolated Docker QA stack. No production URL is accepted. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const { chromium } = require("playwright");

const BASE = process.env.QA_BASE_URL || "http://127.0.0.1:18082";
if (!/^http:\/\/(127\.0\.0\.1|localhost):18082$/.test(BASE)) throw new Error("Refusing non-QA target");
const OUT = process.env.QA_ARTIFACT_DIR || path.resolve(__dirname, "../../../artifacts/audit/browser");
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const errors = [];
let pageForEvidence;

async function scenario(id, title, fn) {
  const started = Date.now();
  try {
    await fn();
    results.push({ id, title, status: "passed", milliseconds: Date.now() - started });
    console.log("PASS", id, title);
  } catch (error) {
    const screenshot = id + "-failure.png";
    try { await pageForEvidence?.screenshot({ path: path.join(OUT, screenshot), fullPage: true }); } catch {}
    results.push({ id, title, status: "failed", milliseconds: Date.now() - started,
      error: String(error.message).slice(0, 1600), screenshot });
    console.log("FAIL", id, error.message);
  }
}
async function signedPage(browser, username, viewport = { width: 1280, height: 900 }) {
  const context = await browser.newContext({ viewport, locale: "fa-IR", timezoneId: "Europe/London" });
  const page = await context.newPage();
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(BASE + "/login/");
  await page.getByLabel("نام کاربری", { exact: true }).fill(username);
  await page.getByLabel("رمز عبور", { exact: true }).fill("qa-system-password-1");
  await page.getByRole("button", { name: "ورود", exact: true }).click();
  await page.waitForURL(BASE + "/", { timeout: 20000 });
  await page.getByRole("heading", { name: "TIME LOG", exact: true }).waitFor();
  return { context, page };
}
async function data(context, url) {
  const response = await context.request.get(BASE + url);
  assert.equal(response.status(), 200, url);
  return response.json();
}
async function post(context, url, body = {}) {
  const response = await context.request.post(BASE + url, {
    data: body, headers: { "X-Requested-With": "timelog" },
  });
  assert.ok(response.ok(), url + ": " + await response.text());
  return response.json();
}
async function mutation(page, url, click) {
  const [response] = await Promise.all([
    page.waitForResponse(r => new URL(r.url()).pathname === url && r.request().method() !== "GET"),
    click(),
  ]);
  assert.ok(response.ok(), await response.text());
}
async function checkRowStatus(context, title, status) {
  const tasks = await data(context, "/api/tasks");
  const task = tasks.find(t => t.title === title);
  assert.ok(task, title);
  assert.equal(task.status, status);
  return task;
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.QA_BROWSER_CHANNEL || "chrome", headless: true });
  let a, b, admin;
  try {
    await scenario("E2E-01", "ورود واقعی کاربر و کوکی ماندگار", async () => {
      a = await signedPage(browser, "qa_alice"); pageForEvidence = a.page;
      const cookie = (await a.context.cookies()).find(c => c.name === "tl_session");
      assert.ok(cookie?.httpOnly && cookie.expires > Date.now() / 1000 + 80 * 86400);
      assert.equal((await data(a.context, "/api/me")).username, "qa_alice");
    });
    if (!a) throw new Error("Login prerequisite failed");

    await scenario("E2E-02", "مدیریت شخصی نوع گزارش، پروژه و استوری", async () => {
      const p = a.page; await p.goto(BASE + "/admin/");
      await p.getByRole("heading", { name: "نوع گزارش، پروژه و استوری‌های من" }).waitFor();
      assert.equal(await p.getByRole("heading", { name: "کاربران", exact: true }).count(), 0);
      await p.getByPlaceholder("نوع گزارش جدید...").fill("فنی QA");
      await mutation(p, "/api/catalog/report-types", () => p.getByPlaceholder("نوع گزارش جدید...").locator("..").getByRole("button", { name: "افزودن", exact: true }).click());
      await p.getByPlaceholder("پروژه‌ی جدید...").fill("پروژه QA");
      await mutation(p, "/api/catalog/projects", () => p.getByRole("button", { name: "افزودن پروژه" }).click());
      await p.getByPlaceholder("استوری جدید برای این پروژه...").fill("استوری QA");
      const projects = (await data(a.context, "/api/catalog")).projects;
      await mutation(p, "/api/catalog/projects/" + projects[0].id + "/stories",
        () => p.getByPlaceholder("استوری جدید برای این پروژه...").locator("..").getByRole("button", { name: "افزودن", exact: true }).click());
      await p.getByText("استوری QA", { exact: true }).waitFor();
    });
    await scenario("E2E-03", "ساخت تگ متصل به استوری از فرم تسک", async () => {
      const p = a.page; await p.goto(BASE + "/");
      await p.getByRole("combobox", { name: "عنوان استوری", exact: true }).selectOption("__new__");
      const dialog = p.getByRole("dialog");
      await dialog.getByRole("combobox", { name: "استوری سامانه‌ی اصلی" }).selectOption({ label: "استوری QA" });
      await dialog.getByRole("combobox", { name: "نوع گزارش", exact: true }).selectOption({ label: "فنی QA" });
      await mutation(p, "/api/tags", () => dialog.getByRole("button", { name: "ساخت تگ" }).click());
    });
    await scenario("E2E-04", "چرخهٔ شروع، مکث، ادامه و پایان تسک", async () => {
      const p = a.page;
      await p.getByLabel("شرح فعالیت", { exact: true }).fill("کار مرورگر QA");
      await mutation(p, "/api/tasks", () => p.getByRole("button", { name: "ثبت تسک ▶", exact: true }).click());
      const row = p.locator(".task-row").filter({ hasText: "کار مرورگر QA" });
      const task = (await data(a.context, "/api/tasks")).find(t => t.title === "کار مرورگر QA");
      await mutation(p, `/api/tasks/${task.id}/pause`, () => row.getByRole("button", { name: "مکث ⏸", exact: true }).click());
      await row.getByRole("button", { name: "ادامه ▶", exact: true }).waitFor();
      await mutation(p, `/api/tasks/${task.id}/resume`, () => row.getByRole("button", { name: "ادامه ▶", exact: true }).click());
      await row.getByRole("button", { name: "پایان ⏹", exact: true }).waitFor();
      await mutation(p, `/api/tasks/${task.id}/stop`, () => row.getByRole("button", { name: "پایان ⏹", exact: true }).click());
      await row.getByText("در حال انجام", { exact: true }).waitFor({ state: "hidden" });
      await checkRowStatus(a.context, "کار مرورگر QA", "done");
    });
    await scenario("E2E-05", "ثبت حضور و پایان کار با تأیید", async () => {
      const p = a.page; await p.goto(BASE + "/");
      await p.locator("#presenceCard").getByRole("button", { name: "ورود", exact: true }).click();
      await p.locator("#presenceCard").getByRole("button", { name: "پایان کار (خروج کامل)", exact: true }).waitFor();
      await p.locator("#presenceCard").getByRole("button", { name: "پایان کار (خروج کامل)", exact: true }).click();
      await p.getByRole("dialog").getByRole("button", { name: "بله، پایان کار" }).click();
      await p.locator("#presenceCard").getByRole("button", { name: "ورود دوباره", exact: true }).waitFor();
      assert.equal((await data(a.context, "/api/presence")).status, "done");
    });
    await scenario("E2E-06", "برنامه‌ریزی، شروع برنامه و پایان", async () => {
      const p = a.page; await p.goto(BASE + "/planned/");
      await p.getByRole("textbox", { name: "شرح فعالیت برنامه‌ریزی‌شده" }).fill("برنامه QA");
      await mutation(p, "/api/planned", () => p.getByRole("button", { name: "افزودن به برنامه ▶" }).click());
      const row = p.locator(".task-row").filter({ hasText: "برنامه QA" });
      const planned = (await data(a.context, "/api/planned")).find(item => item.title === "برنامه QA");
      await mutation(p, "/api/planned/" + planned.id + "/start",
        () => row.getByRole("button", { name: "شروع ▶", exact: true }).click());
      const tasks = await data(a.context, "/api/tasks");
      const running = tasks.find(t => t.title === "برنامه QA");
      assert.equal(running?.planned_flag, true);
      await post(a.context, "/api/tasks/" + running.id + "/stop");
    });
    await scenario("E2E-07", "مقاومت در برابر اجرای HTML ورودی کاربر", async () => {
      const title = '<img src=x onerror="window.__qaXss=1"> QA';
      await post(a.context, "/api/tasks", { title, start_time: "03:00", end_time: "03:01" });
      await a.page.goto(BASE + "/tasks/");
      await a.page.getByText(title, { exact: true }).waitFor();
      assert.equal(await a.page.locator("img[src=x]").count(), 0);
      assert.equal(await a.page.evaluate(() => window.__qaXss), undefined);
    });
    await scenario("E2E-08", "دو حساب مستقل در مرورگر", async () => {
      b = await signedPage(browser, "qa_bob"); pageForEvidence = b.page;
      assert.deepEqual(await data(b.context, "/api/tasks"), []);
      await b.page.goto(BASE + "/admin/");
      assert.equal((await data(b.context, "/api/catalog")).projects.length, 0);
      assert.equal(await b.page.getByText("پروژه QA", { exact: true }).count(), 0);
    });
    await scenario("E2E-09", "قطع شبکه، حفظ فرم و ارسال پس از اتصال", async () => {
      const p = b.page; await p.goto(BASE + "/");
      await p.getByLabel("شرح فعالیت", { exact: true }).fill("آفلاین QA");
      await b.context.setOffline(true);
      await p.getByRole("button", { name: "ثبت تسک ▶", exact: true }).click();
      await p.getByRole("alert").filter({ hasText: "ارتباط با سرور برقرار نشد" }).waitFor();
      assert.equal(await p.getByLabel("شرح فعالیت", { exact: true }).inputValue(), "آفلاین QA");
      await b.context.setOffline(false);
      await mutation(p, "/api/tasks", () => p.getByRole("button", { name: "ثبت تسک ▶", exact: true }).click());
      const running = await checkRowStatus(b.context, "آفلاین QA", "running");
      await post(b.context, "/api/tasks/" + running.id + "/stop");
    });
    await scenario("E2E-10", "ادمین حساب می‌سازد و کاتالوگ دیگران را نمی‌بیند", async () => {
      admin = await signedPage(browser, "qa_admin"); pageForEvidence = admin.page;
      await admin.page.goto(BASE + "/admin/");
      await admin.page.getByRole("heading", { name: "کاربران", exact: true }).waitFor();
      await admin.page.getByPlaceholder("نام کاربری (حروف لاتین کوچک)").fill("qa_invited");
      await mutation(admin.page, "/api/admin/users",
        () => admin.page.getByRole("button", { name: "ساخت کاربر (رمز موقت ساخته می‌شود)" }).click());
      await admin.page.getByRole("button", { name: "بستن", exact: true }).click();
      assert.equal((await data(admin.context, "/api/catalog")).projects.length, 0);
    });
    await scenario("E2E-11", "ورود ماندگار پس از بستن واقعی مرورگر تست", async () => {
      const profile = fs.mkdtempSync(path.join(os.tmpdir(), "timelog-qa-browser-"));
      const options = { channel: process.env.QA_BROWSER_CHANNEL || "chrome", headless: true, viewport: { width: 1280, height: 900 } };
      let context;
      try {
        context = await chromium.launchPersistentContext(profile, options);
        await context.addCookies(await a.context.cookies());
        let p = await context.newPage(); await p.goto(BASE + "/");
        assert.equal((await data(context, "/api/me")).username, "qa_alice");
        await context.close(); context = null;
        context = await chromium.launchPersistentContext(profile, options);
        p = await context.newPage(); await p.goto(BASE + "/login/");
        await p.waitForURL(BASE + "/", { timeout: 15000 });
        assert.equal((await data(context, "/api/me")).username, "qa_alice");
      } finally {
        if (context) await context.close();
        assert.equal(path.dirname(profile), os.tmpdir());
        assert.ok(path.basename(profile).startsWith("timelog-qa-browser-"));
        fs.rmSync(profile, { recursive: true, force: true });
      }
    });

    const routes = ["/", "/planned/", "/dashboard/", "/calendar/", "/timesheet/", "/tasks/", "/daylog/", "/settings/", "/admin/"];
    let index = 20;
    for (const width of [360, 768, 1280]) {
      await a.page.setViewportSize({ width, height: 900 });
      for (const route of routes) {
        await scenario("E2E-" + index++, "نمایش " + route + " در عرض " + width, async () => {
          pageForEvidence = a.page; await a.page.goto(BASE + route);
          await a.page.locator("main").waitFor();
          await a.page.waitForFunction(() => document.querySelector("main")?.textContent.trim().length > 20);
          assert.equal(await a.page.locator("html").getAttribute("dir"), "rtl");
          const sizes = await a.page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, width: innerWidth }));
          assert.ok(sizes.scroll <= sizes.width + 1, JSON.stringify(sizes));
          if (["/", "/daylog/", "/admin/"].includes(route))
            await a.page.screenshot({ path: path.join(OUT, "width-" + width + "-" + (route === "/" ? "today" : route.split("/")[1]) + ".png"), fullPage: true });
        });
      }
    }
    await scenario("E2E-50", "ناوبری پایین موبایل", async () => {
      await a.page.setViewportSize({ width: 360, height: 740 }); await a.page.goto(BASE + "/");
      await a.page.locator(".bottom-nav").getByRole("link", { name: /گزارش روزانه/ }).click();
      await a.page.waitForURL(BASE + "/daylog/");
      await a.page.locator(".bottom-nav").getByRole("button", { name: /بیشتر/ }).click();
      await a.page.locator(".sheet-menu").getByRole("link", { name: /مدیریت/ }).click();
      await a.page.waitForURL(BASE + "/admin/");
    });
    await scenario("E2E-51", "خروج حساب و رد شدن کوکی قدیمی", async () => {
      const oldCookie = (await b.context.cookies()).find(c => c.name === "tl_session");
      await post(b.context, "/api/auth/logout");
      const response = await b.context.request.get(BASE + "/api/me", { headers: { Cookie: "tl_session=" + oldCookie.value } });
      assert.equal(response.status(), 401);
    });

    await scenario("E2E-53", "چرخهٔ تسک با لمس واقعی در نمای موبایل", async () => {
      const context = await browser.newContext({ viewport: { width: 360, height: 740 }, hasTouch: true, isMobile: true });
      try {
        await context.addCookies(await a.context.cookies());
        const p = await context.newPage(); pageForEvidence = p;
        p.on("pageerror", e => errors.push(e.message));
        await p.goto(BASE + "/");
        assert.ok(await p.evaluate(() => navigator.maxTouchPoints > 0));
        await p.getByLabel("شرح فعالیت", { exact: true }).fill("کار لمسی QA");
        await mutation(p, "/api/tasks", () => p.getByRole("button", { name: "ثبت تسک ▶", exact: true }).tap());
        const row = p.locator(".task-row").filter({ hasText: "کار لمسی QA" });
        const task = (await data(a.context, "/api/tasks")).find(t => t.title === "کار لمسی QA");
        await mutation(p, `/api/tasks/${task.id}/pause`, () => row.getByRole("button", { name: "مکث ⏸", exact: true }).tap());
        await mutation(p, `/api/tasks/${task.id}/resume`, () => row.getByRole("button", { name: "ادامه ▶", exact: true }).tap());
        await mutation(p, `/api/tasks/${task.id}/stop`, () => row.getByRole("button", { name: "پایان ⏹", exact: true }).tap());
        await row.getByText("در حال انجام", { exact: true }).waitFor({ state: "hidden" });
        await checkRowStatus(a.context, "کار لمسی QA", "done");
        await p.screenshot({ path: path.join(OUT, "mobile-touch.png"), fullPage: true });
      } finally { await context.close(); }
    });
    await scenario("E2E-54", "نمایش ساعت تهران در مرورگر با منطقهٔ زمانی لندن", async () => {
      await a.page.goto(BASE + "/");
      await a.page.locator(".clock").waitFor();
      const clock = (await a.page.locator(".clock").innerText()).replace(/[۰-۹]/g, d => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d))).replace(/[^0-9:]/g, "");
      const today = await data(a.context, "/api/today");
      const minutes = value => { const [h, m] = value.split(":").map(Number); return h * 60 + m; };
      const difference = Math.abs(minutes(clock) - minutes(today.time));
      assert.ok(Math.min(difference, 1440 - difference) <= 1, clock + " vs " + today.time);
    });
    await scenario("E2E-56", "پیش‌نمایش، ثبت و بازگردانی تکمیل ساعت از UI", async () => {
      for (const [title, start_time, end_time] of [["تکمیل اول QA", "12:00", "14:00"], ["تکمیل دوم QA", "14:00", "16:00"]])
        await post(a.context, "/api/tasks", { title, start_time, end_time });
      const presence = await data(a.context, "/api/presence");
      const response = await a.context.request.put(BASE + "/api/presence/" + presence.segments[0].id,
        { data: { start_time: "08:00", end_time: "16:00" }, headers: { "X-Requested-With": "timelog" } });
      assert.ok(response.ok());
      const before = (await data(a.context, "/api/tasks")).map(t => [t.id, t.duration_minutes]);
      await a.page.goto(BASE + "/");
      await a.page.locator("#presenceCard").getByRole("button", { name: "تکمیل ساعت گزارش", exact: true }).click();
      let dialog = a.page.getByRole("dialog");
      await dialog.getByRole("button", { name: "ادامه و پیش‌نمایش ←" }).click();
      await dialog.getByRole("button", { name: "تأیید نهایی و ثبت" }).waitFor();
      await a.page.screenshot({ path: path.join(OUT, "fill-preview.png"), fullPage: true });
      await mutation(a.page, "/api/fill", () => dialog.getByRole("button", { name: "تأیید نهایی و ثبت" }).click());
      const after = await data(a.context, "/api/tasks");
      assert.ok(after.reduce((sum, t) => sum + t.fill_minutes, 0) > 0);
      assert.deepEqual(after.map(t => [t.id, t.duration_minutes]), before);
      await a.page.locator("#presenceCard").getByRole("button", { name: "↶ برگرداندن به زمان ثبت‌شده", exact: true }).click();
      dialog = a.page.getByRole("dialog");
      await mutation(a.page, "/api/fill/rollback", () => dialog.getByRole("button", { name: "بله، برگردان" }).click());
      assert.ok((await data(a.context, "/api/tasks")).every(t => t.fill_minutes === 0));
      await post(a.context, "/api/planned", { title: "برنامهٔ باقی‌مانده برای تست بازیابی" });
    });
    await scenario("E2E-57", "متن HTML اجرا نمی‌شود و CSP اسکریپت تزریق‌شده را مسدود می‌کند", async () => {
      const title = '<img src=x onerror="window.__audit_xss=1">';
      await post(a.context, "/api/tasks", { title, start_time: "01:01", end_time: "01:02" });
      await a.page.goto(BASE + "/");
      const row = a.page.locator(".task-row").filter({hasText:title});
      await row.waitFor(); assert.equal(await row.locator("img").count(), 0);
      await a.page.evaluate(() => { const script=document.createElement("script"); script.textContent="window.__audit_csp=1"; document.body.appendChild(script); });
      assert.ok(await a.page.evaluate(() => !window.__audit_xss && !window.__audit_csp));
    });
    await scenario("E2E-58", "ورود کاربر غیرفعال رد می‌شود", async () => {
      const context=await browser.newContext();
      try {
        const page=await context.newPage();await page.goto(BASE+"/login/");
        await page.getByLabel("نام کاربری",{exact:true}).fill("qa_inactive");
        await page.getByLabel("رمز عبور",{exact:true}).fill("qa-system-password-1");
        const [response]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==="/api/auth/login"),page.getByRole("button",{name:"ورود",exact:true}).click()]);
        assert.equal(response.status(),401); assert.ok(page.url().includes("/login/"));
      } finally {await context.close();}
    });
    await scenario("E2E-55", "نبود خطای JavaScript در مرور صفحه‌ها", async () => assert.deepEqual(errors, []));
  } finally {
    await browser.close();
    const report = { generatedAt: new Date().toISOString(), browser: "Chromium/Chrome", base: BASE, results, pageErrors: errors };
    fs.writeFileSync(path.join(OUT, "e2e.json"), JSON.stringify(report, null, 2));
  }
  if (results.some(r => r.status === "failed")) process.exitCode = 1;
})().catch(error => { console.error(error.message); process.exitCode = 1; });
