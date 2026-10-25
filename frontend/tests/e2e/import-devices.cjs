/* Same-account desktop/mobile sessions, actual import UI and network-failure recovery. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const BASE='http://127.0.0.1:18082';
const OUT=path.resolve(__dirname,'../../../artifacts/audit/import-devices');fs.mkdirSync(OUT,{recursive:true});
const results=[];const errors=[];
async function test(name,fn){try{await fn();results.push({name,status:'passed'});console.log('PASS',name);}catch(e){results.push({name,status:'failed',error:String(e.message)});console.log('FAIL',name,e.message);}}
async function login(browser,username,password,mobile=false){
 const ctx=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},hasTouch:mobile,isMobile:mobile,locale:'fa-IR'});
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(BASE+'/login/');
 await page.getByLabel('نام کاربری',{exact:true}).fill(username);await page.getByLabel('رمز عبور',{exact:true}).fill(password);
 await page.getByRole('button',{name:'ورود',exact:true}).click();await page.waitForURL(BASE+'/');await page.getByRole('heading',{name:'TIME LOG',exact:true}).waitFor();
 await page.waitForLoadState('networkidle');
 if(await page.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).isVisible())await page.getByRole('button',{name:'فعلاً بدون شیت ادامه می‌دهم',exact:true}).click();
 return {ctx,page};
}
(async()=>{const browser=await chromium.launch({channel:process.env.QA_BROWSER_CHANNEL||'chrome',headless:true});
try{
 const admin=await login(browser,'qa_admin','qa-system-password-1');
 const response=await admin.ctx.request.post(BASE+'/api/admin/users',{headers:{'X-Requested-With':'timelog'},data:{username:'qa_transfer_'+Date.now(),display_name:'Import and devices'}});assert.equal(response.status(),201);const account=await response.json();await admin.ctx.close();
 const desktop=await login(browser,account.username,account.temp_password);
 const mobile=await login(browser,account.username,account.temp_password,true);
 await test('Independent same-account sessions survive concurrent sign-in',async()=>{
  const a=(await desktop.ctx.cookies()).find(c=>c.name==='tl_session');const b=(await mobile.ctx.cookies()).find(c=>c.name==='tl_session');assert.ok(a&&b&&a.value!==b.value);
  for(const ctx of [desktop.ctx,mobile.ctx])assert.equal((await (await ctx.request.get(BASE+'/api/me')).json()).username,account.username);
 });
 await desktop.page.goto(BASE+'/settings/');
 await test('Download Excel, CSV and model-conversion guide from Settings',async()=>{
  for(const [label,ext]of [['نمونهٔ اکسل ↓','xlsx'],['نمونهٔ CSV ↓','csv'],['راهنمای تبدیل برای مدل ↓','txt']]){
   const [download]=await Promise.all([desktop.page.waitForEvent('download'),desktop.page.getByRole('link',{name:label,exact:true}).click()]);
   assert.ok(download.suggestedFilename().endsWith('.'+ext));await download.saveAs(path.join(OUT,'template.'+ext));
  }
 });
 await desktop.page.goto(BASE+'/');
 const today=await (await desktop.ctx.request.get(BASE+'/api/today')).json();const day=`${today.jalali_year}/${today.jalali_month}/${today.jalali_day}`;
 const title=('سابقه منتقل‌شده '+ 'آزمایش متن بلند '.repeat(12)).trim();
 const valid=Buffer.from(`روز,کار انجام شده,دقیقه کار\n${day},${title},90.25\n${day},دومین سابقه,60\n`,'utf8');
 const invalid=Buffer.from('date,title,duration\ninvalid,bad,60\n','utf8');
 const page=mobile.page;await page.goto(BASE+'/settings/');
 await test('A bad file shows source-row errors and imports nothing',async()=>{
  await page.getByLabel('فایل سابقه (XLSX یا CSV، حداکثر ۵ مگابایت و ۵۰۰۰ سطر)').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:invalid});
  await page.getByRole('button',{name:'پیش‌نمایش فایل',exact:true}).click();await page.getByText(/تا رفع خطاها هیچ ردیفی وارد نمی‌شود/).waitFor();
  assert.ok(await page.getByRole('button',{name:/تأیید و واردکردن/}).isDisabled());assert.deepEqual(await (await mobile.ctx.request.get(BASE+'/api/tasks')).json(),[]);
 });
 await test('Custom columns can be mapped with a clean second preview',async()=>{
  await page.getByLabel('فایل سابقه (XLSX یا CSV، حداکثر ۵ مگابایت و ۵۰۰۰ سطر)').setInputFiles({name:'history.csv',mimeType:'text/csv',buffer:valid});
  await page.getByRole('button',{name:'پیش‌نمایش فایل',exact:true}).click();
  await page.getByLabel('ستون تاریخ',{exact:true}).selectOption('روز');
  await page.getByLabel('ستون شرح فعالیت',{exact:true}).selectOption('کار انجام شده');
  await page.getByLabel('ستون مدت (دقیقه)',{exact:true}).selectOption('دقیقه کار');
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/me/import/preview')),page.getByRole('button',{name:'پیش‌نمایش فایل',exact:true}).click()]);
  const preview=await response.json();assert.equal(preview.new_rows,2);assert.equal(preview.new_minutes,150.25);assert.equal(preview.error_count,0);
  await page.waitForFunction(()=>!document.querySelector(".import-review details")?.open);
  assert.equal(await page.getByText("انتخاب یا اصلاح ستون‌ها",{exact:true}).evaluate(e=>e.parentElement.open),false);
  await page.getByRole('button',{name:/تأیید و واردکردن/}).waitFor();
  await page.screenshot({path:path.join(OUT,'mobile-import-preview.png'),fullPage:true});
 });
 await test('Lost commit response and retry do not duplicate or lose records',async()=>{
  await page.route('**/api/me/import/commit',async route=>{const response=await route.fetch();assert.ok(response.ok());await route.abort('failed');});
  const submit=page.getByRole('button',{name:/تأیید و واردکردن/});await submit.click();await page.getByRole('alert').filter({hasText:'ارتباط با سرور برقرار نشد'}).waitFor();
  assert.equal(await page.locator('#import-file').evaluate(e=>e.files[0].name),'history.csv');
  await page.unroute('**/api/me/import/commit');
  const [response]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/api/me/import/commit')),submit.click()]);assert.equal(response.status(),200);assert.equal((await response.json()).imported,0);
  await page.getByRole('status').filter({hasText:/ردیف تکراری وارد نشد/}).waitFor();
  const tasks=await (await mobile.ctx.request.get(BASE+'/api/tasks')).json();assert.equal(tasks.length,2);assert.equal(tasks.reduce((a,t)=>a+t.duration_minutes,0),150.25);
 });
 await test('Desktop sees the phone import without reloading',async()=>{await desktop.page.locator('.task-row').filter({hasText:title}).waitFor({timeout:25000});});
 await test('Phone sees a desktop change through periodic refresh',async()=>{
  await page.goto(BASE+'/');await page.locator('.task-row').filter({hasText:title}).waitFor();
  const tasks=await (await desktop.ctx.request.get(BASE+'/api/tasks')).json();const task=tasks.find(t=>t.title===title);
  const response=await desktop.ctx.request.put(BASE+'/api/tasks/'+task.id,{headers:{'X-Requested-With':'timelog'},data:{title:'ویرایش از کامپیوتر'}});assert.equal(response.status(),200);
  await page.locator('.task-row').filter({hasText:'ویرایش از کامپیوتر'}).waitFor({timeout:25000});
  const other=tasks.find(t=>t.title==='دومین سابقه');await page.locator('.task-row').filter({hasText:'دومین سابقه'}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();const titleInput=dialog.getByRole('textbox',{name:'شرح فعالیت',exact:true});
  // Use the labelled task-description field when present; the first textbox is the title in this dialog.
  await titleInput.fill('ویرایش از گوشی');
  const [saved]=await Promise.all([page.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+other.id&&r.request().method()==='PUT'),dialog.getByRole('button',{name:'ذخیره',exact:true}).click()]);assert.equal(saved.status(),200);
  await desktop.page.locator('.task-row').filter({hasText:'ویرایش از گوشی'}).waitFor({timeout:25000});
  await page.screenshot({path:path.join(OUT,'mobile-shared-account.png'),fullPage:true});await desktop.page.screenshot({path:path.join(OUT,'desktop-shared-account.png'),fullPage:true});
 });
 await test('Concurrent edit conflict preserves the draft and newer server data',async()=>{
  const p=desktop.page;await p.locator('.task-row').filter({hasText:'ویرایش از گوشی'}).click();const dialog=p.getByRole('dialog');await dialog.waitFor();
  const input=dialog.getByRole('textbox',{name:'شرح فعالیت',exact:true});await input.fill('پیش‌نویس ذخیره‌نشدهٔ کامپیوتر');
  const tasks=await (await mobile.ctx.request.get(BASE+'/api/tasks')).json();const task=tasks.find(t=>t.title==='ویرایش از گوشی');
  const remote=await mobile.ctx.request.put(BASE+'/api/tasks/'+task.id,{headers:{'X-Requested-With':'timelog'},data:{title:'نسخهٔ جدید از گوشی'}});assert.equal(remote.status(),200);
  const [response]=await Promise.all([p.waitForResponse(r=>new URL(r.url()).pathname==='/api/tasks/'+task.id&&r.request().method()==='PUT'),dialog.getByRole('button',{name:'ذخیره',exact:true}).click()]);assert.equal(response.status(),409);
  assert.equal(await input.inputValue(),'پیش‌نویس ذخیره‌نشدهٔ کامپیوتر');
  const saved=(await (await mobile.ctx.request.get(BASE+'/api/tasks')).json()).find(t=>t.id===task.id);assert.equal(saved.title,'نسخهٔ جدید از گوشی');assert.equal(saved.duration_minutes,task.duration_minutes);
  await p.keyboard.press('Escape');await p.getByRole('button',{name:'بله، ببند',exact:true}).click();
 });
 await test('Logging out on the phone preserves the desktop session',async()=>{
  const response=await mobile.ctx.request.post(BASE+'/api/auth/logout',{headers:{'X-Requested-With':'timelog'}});assert.equal(response.status(),200);
  assert.equal((await desktop.ctx.request.get(BASE+'/api/me')).status(),200);assert.equal((await mobile.ctx.request.get(BASE+'/api/me')).status(),401);
 });
 await test('No uncaught browser JavaScript errors',()=>assert.deepEqual(errors,[]));
 await desktop.ctx.close();await mobile.ctx.close();
}finally{await browser.close();fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify({results,errors},null,2));console.log(JSON.stringify({passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').length}));if(results.some(r=>r.status==='failed'))process.exitCode=1;}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
