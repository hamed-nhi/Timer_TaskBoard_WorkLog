/* Isolated audit-only tests. Real-provider availability is not asserted without keys. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs'); const path = require('node:path');
const BASE = 'http://127.0.0.1:18082';
const OUT = path.resolve(__dirname, '../../../artifacts/audit/login-security'); fs.mkdirSync(OUT, { recursive: true });
let adminName = 'qa_admin', adminPassword = 'qa-system-password-1';
if (process.env.QA_CREDENTIALS_FILE) {
  const line = fs.readFileSync(process.env.QA_CREDENTIALS_FILE, 'utf8').split(/\r?\n/).find(l => l.split(' | ')[1] === 'administrator');
  assert.ok(line, 'Private admin credentials required'); [adminName, , adminPassword] = line.split(' | ');
}
const headers = { 'X-Requested-With': 'timelog' }; const results = []; const errors = [];
async function test(name, fn) { try { await fn(); results.push({ name, status: 'passed' }); console.log('PASS', name); } catch (e) { results.push({ name, status: 'failed', error: e.message }); console.log('FAIL', name, e.message); throw e; } }
async function pause(ms) { await new Promise(r => setTimeout(r, ms)); }
(async () => {
 for(let i=0;i<60;i++){try{if((await fetch(BASE+'/api/health')).ok)break;}catch{}await pause(500);}
 const browser = await chromium.launch({ channel: process.env.QA_BROWSER_CHANNEL || 'chrome', headless: true });
 const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'fa-IR', timezoneId: 'Asia/Tehran', bypassCSP: true });
 const page = await ctx.newPage(); page.on('pageerror', e => errors.push(e.message)); let originalPolicy;
 const member = 'qa_guard_' + Date.now(); const renamed = member + '_new'; const initial = 'Qa-chosen-password-1!'; const changed = 'Qa-changed-password-2!';
 try {
  await test('Administrator login and security panel load', async () => {
   await page.goto(BASE + '/login/'); await page.getByLabel('نام کاربری', { exact: true }).fill(adminName); await page.getByLabel('رمز عبور', { exact: true }).fill(adminPassword);
   await page.getByRole('button', { name: 'ورود', exact: true }).click(); await page.waitForURL(BASE + '/');
   await page.waitForLoadState('networkidle');
   if(await page.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).isVisible())await page.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).click();
   await page.goto(BASE + '/admin/');
   await page.getByRole('heading', { name: 'امنیت ورود و مسدودی‌ها', exact: true }).waitFor();
   const response = await ctx.request.get(BASE + '/api/admin/login-protection'); assert.equal(response.status(), 200); originalPolicy = (await response.json()).policy;
  });
  await test('Create ordinary account with chosen password from UI', async () => {
   await page.getByPlaceholder('نام کاربری (حروف لاتین کوچک)').fill(member); await page.getByPlaceholder('نام نمایشی', { exact: true }).fill('Security UI fixture');
   await page.getByLabel('رمز اولیه (خالی = ساخت رمز تصادفی)', { exact: true }).fill(initial);
   const [r] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/admin/users') && r.request().method() === 'POST'), page.getByRole('button', { name: 'ساخت کاربر', exact: true }).click()]); assert.equal(r.status(), 201);
   await page.locator('.presence-note').getByRole('button', { name: 'بستن', exact: true }).click();
   const users = await (await ctx.request.get(BASE + '/api/admin/users')).json(); const u = users.find(u => u.username === member); assert.ok(u && !u.is_admin);
  });
  await test('Forged IP headers do not bypass three-attempt ban through Caddy', async () => {
   for (let i = 0; i < 3; i++) { const r = await ctx.request.post(BASE + '/api/auth/login', { headers: { ...headers, 'X-Forwarded-For': '192.0.2.' + (i + 1), 'Forwarded': 'for=203.0.113.99' }, data: { username: member, password: 'wrong-password' } }); assert.equal(r.status(), 401); }
   const r = await ctx.request.post(BASE + '/api/auth/login', { headers, data: { username: member, password: initial } }); assert.equal(r.status(), 429); assert.ok(Number(r.headers()['retry-after']) > 800);
   const bans = (await (await ctx.request.get(BASE + '/api/admin/login-protection')).json()).bans.filter(b => b.username === member); assert.equal(bans.length, 1); assert.equal(bans[0].stage, 1); assert.ok(bans[0].active); assert.ok(!bans[0].ip.startsWith('192.0.2.'));
  });
  await test('Admin can release ban graphically while keeping its stage', async () => {
   await page.reload(); const row = page.locator('.login-security tbody tr').filter({ has: page.getByText(member, { exact: true }) }); await row.getByRole('button', { name: 'رفع بن', exact: true }).click();
   await page.getByRole('dialog').getByRole('button', { name: 'تأیید', exact: true }).click();
   await row.getByRole('button', { name: 'رفع بن', exact: true }).waitFor(); await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
   await page.waitForFunction(name => [...document.querySelectorAll('.login-security tbody tr')].find(r => r.textContent.includes(name))?.textContent.includes('آزاد'), member);
  });
  let userContext; let taskId;
  await test('Ordinary session works after release and cannot use admin controls', async () => {
   userContext = await browser.newContext(); const login = await userContext.request.post(BASE + '/api/auth/login', { headers, data: { username: member, password: initial } }); assert.equal(login.status(), 200);
   assert.equal((await userContext.request.get(BASE + '/api/admin/login-protection')).status(), 403);
   const r = await userContext.request.post(BASE + '/api/tasks', { headers, data: { title: 'Retain this task after account changes', jalali_date: '1405/07/01', start_time: '09:00', end_time: '10:00' } }); assert.equal(r.status(), 201); taskId = (await r.json()).id;
  });
  await test('Rename and password change from UI revoke old session, preserve tasks', async () => {
   const row = page.locator('.user-table tbody tr').filter({ has: page.getByText(member, { exact: true }) }); await row.getByRole('button', { name: 'ویرایش حساب', exact: true }).click();
   const dialog = page.getByRole('dialog'); await dialog.getByLabel('نام کاربری جدید', { exact: true }).fill(renamed); await dialog.getByLabel('رمز جدید (خالی = بدون تغییر)', { exact: true }).fill(changed);
   await dialog.getByRole('button', { name: 'ذخیره حساب', exact: true }).click(); await dialog.waitFor({ state: 'hidden' });
   assert.equal((await userContext.request.get(BASE + '/api/me')).status(), 401);
   assert.equal((await userContext.request.post(BASE + '/api/auth/login', { headers, data: { username: renamed, password: changed } })).status(), 200);
   assert.ok((await (await userContext.request.get(BASE + '/api/tasks')).json()).some(t => t.id === taskId && t.duration_minutes === 60));
  });
  await test('Deactivate and reactivate preserves data; deletion endpoint is absent', async () => {
   const users = await (await ctx.request.get(BASE + '/api/admin/users')).json(); const uid = users.find(u => u.username === renamed).id;
   const row = page.locator('.user-table tbody tr').filter({ has: page.getByText(renamed, { exact: true }) }); await row.getByRole('button', { name: 'غیرفعال کن', exact: true }).click(); await row.getByRole('button', { name: 'فعال کن', exact: true }).waitFor();
   assert.equal((await userContext.request.get(BASE + '/api/me')).status(), 401); assert.equal((await ctx.request.delete(BASE + '/api/admin/users/' + uid, { headers })).status(), 405);
   await row.getByRole('button', { name: 'فعال کن', exact: true }).click(); await row.getByRole('button', { name: 'غیرفعال کن', exact: true }).waitFor();
   assert.equal((await userContext.request.post(BASE + '/api/auth/login', { headers, data: { username: renamed, password: changed } })).status(), 200);
   assert.ok((await (await userContext.request.get(BASE + '/api/tasks')).json()).some(t => t.id === taskId && t.duration_minutes === 60));
  });
  await test('Policy can be edited in UI and restored without extending existing bans', async () => {
   await page.getByLabel('تعداد رمز اشتباه در هر مرحله', { exact: true }).fill('4');
   const [response] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/api/admin/login-protection') && r.request().method() === 'PUT'), page.getByRole('button', { name: 'ذخیره سیاست ورود', exact: true }).click()]); assert.equal(response.status(), 200);
   assert.equal((await (await ctx.request.get(BASE + '/api/admin/login-protection')).json()).policy.attempts, 4);
   assert.equal((await ctx.request.put(BASE + '/api/admin/login-protection', { headers, data: originalPolicy })).status(), 200);
  });
  await test('Three unknown names ban IP for 24h; existing admin can clear it', async () => {
   for (let i = 0; i < 3; i++) assert.equal((await ctx.request.post(BASE + '/api/auth/login', { headers, data: { username: 'qa_nonexistent_guard_' + i, password: 'wrong-password' } })).status(), 401);
   const r = await ctx.request.post(BASE + '/api/auth/login', { headers, data: { username: renamed, password: changed } }); assert.equal(r.status(), 429); assert.ok(Number(r.headers()['retry-after']) > 86300);
   assert.equal((await ctx.request.get(BASE + '/api/me')).status(), 200);
   await page.reload(); const row = page.locator('.login-security tbody tr').filter({ has: page.getByText('نام ناشناس', { exact: true }) }); await row.getByRole('button', { name: 'پاک‌کردن سابقه', exact: true }).click();
   await page.getByRole('dialog').getByRole('button', { name: 'تأیید', exact: true }).click(); await row.waitFor({ state: 'hidden' });
  });
  await test('Admin page fits desktop/mobile and passes focused axe checks', async () => {
   const axe = fs.readFileSync(path.resolve(__dirname, '../../../tools/qa-browser/node_modules/axe-core/axe.min.js'), 'utf8');
   for (const width of [390, 1440]) { await page.setViewportSize({ width, height: 1000 }); await page.evaluate(axe); const report = await page.evaluate(async () => window.axe.run('.login-security')); assert.deepEqual(report.violations.map(v => v.id), []); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)); await page.screenshot({ path: path.join(OUT, 'admin-' + width + '.png'), fullPage: true }); }
  });
  await test('Optional captcha UI waits for backend config, token and expiry', async () => {
   const c = await browser.newContext(); const p = await c.newPage();
   await p.route('**/api/auth/config', route => route.fulfill({ json: { captcha_provider: 'arcaptcha', site_key: 'public-fixture-site' } }));
   await p.route('https://nwidget.arcaptcha.ir/1/api.js', route => route.fulfill({ contentType: 'text/javascript', body: 'window.arcaptcha={render:function(selector,options){window.captchaFixture=options; document.querySelector(selector).textContent="Captcha contract fixture";}};' }));
   await p.goto(BASE + '/login/'); await p.waitForFunction(() => window.captchaFixture);
   const submit = p.getByRole('button', { name: 'ورود', exact: true }); assert.equal(await submit.isDisabled(), true);
   await p.evaluate(() => window.captchaFixture.callback('one-use-fixture-token')); assert.equal(await submit.isEnabled(), true);
   await p.evaluate(() => window.captchaFixture.expired_callback()); assert.equal(await submit.isDisabled(), true);
   await c.close();
  });
  await test('First-login backup setup, private Excel and self-service password change', async () => {
   const p=await userContext.newPage();await p.goto(BASE+'/settings/');
   await p.getByRole('heading',{name:'اولین قدم: از داده‌هایتان نسخهٔ پشتیبان داشته باشید',exact:true}).waitFor();
   const [download]=await Promise.all([p.waitForEvent('download'),p.getByRole('link',{name:'دانلود داده‌های من به Excel',exact:true}).click()]);assert.ok(download.suggestedFilename().endsWith('.xlsx'));
   await p.getByLabel('لینک Google Sheet شخصی',{exact:true}).fill('https://attacker.example');await p.getByRole('button',{name:'ذخیره لینک و ادامه',exact:true}).click();
   await p.getByRole('alert').filter({hasText:'Google Sheet'}).waitFor();assert.equal((await (await userContext.request.get(BASE+'/api/settings')).json()).backup_setup_done,false);
   await p.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).click();
   await p.getByRole('heading',{name:'تغییر رمز عبور',exact:true}).waitFor();
   const other=await browser.newContext();assert.equal((await other.request.post(BASE+'/api/auth/login',{headers,data:{username:renamed,password:changed}})).status(),200);
   await p.getByPlaceholder('رمز فعلی',{exact:true}).fill(changed);await p.getByPlaceholder('رمز جدید (حداقل ۸ کاراکتر)',{exact:true}).fill('Member#42');
   await p.getByRole('button',{name:'تغییر رمز',exact:true}).click();await p.getByRole('alert').filter({hasText:'رمز عبور تغییر کرد'}).waitFor();
   assert.equal((await other.request.get(BASE+'/api/me')).status(),401);assert.equal((await userContext.request.get(BASE+'/api/me')).status(),200);
   await p.reload();await p.getByRole('heading',{name:'تغییر رمز عبور',exact:true}).waitFor();assert.equal(await p.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).count(),0);
   await other.close();await p.close();
  });
  await test('1000-request burst is rejected early and service recovers', async () => {
   let next = 0; const statuses = []; await Promise.all(Array.from({ length: 30 }, async () => { while (next++ < 1000) statuses.push((await ctx.request.get(BASE + '/api/health')).status()); }));
   assert.ok(statuses.includes(429)); assert.ok(statuses.every(s => s === 200 || s === 429));
   fs.writeFileSync(path.join(OUT, 'burst.json'), JSON.stringify({ requests: statuses.length, accepted: statuses.filter(s => s === 200).length, limited: statuses.filter(s => s === 429).length, unexpected: statuses.filter(s => s !== 200 && s !== 429).length }));
   await pause(2200); assert.equal((await ctx.request.get(BASE + '/api/me')).status(), 200);
  });
  await test('No uncaught JavaScript errors', async () => assert.deepEqual(errors, []));
 } finally {
  if (originalPolicy) { await pause(2200); await ctx.request.put(BASE + '/api/admin/login-protection', { headers, data: originalPolicy }); }
  fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify({ results }, null, 2)); await browser.close();
 }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
