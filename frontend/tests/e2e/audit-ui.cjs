/* Full route/theme/viewport matrix; isolated browser cookies, audit port only. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:18082';
if(!/^http:\/\/(127\.0\.0\.1|localhost):18082$/.test(BASE))throw Error('Audit target required');
const OUT=path.resolve(__dirname,'../../../artifacts/audit/ui');fs.mkdirSync(OUT,{recursive:true});
const axe=fs.readFileSync(path.resolve(__dirname,'../../../tools/qa-browser/node_modules/axe-core/axe.min.js'),'utf8');
const results=[],errors=[];
async function test(name,fn){try{await fn();results.push({name,status:'passed'});}catch(e){results.push({name,status:'failed',error:String(e.message)});console.log('FAIL',name,e.message.slice(0,220));}}
(async()=>{const browser=await chromium.launch({channel:process.env.QA_BROWSER_CHANNEL||'chrome',headless:true});
try{for(const user of ['qa_alice','qa_admin']){
 const ctx=await browser.newContext({locale:'fa-IR',timezoneId:'Asia/Tehran',bypassCSP:true});
 const login=await ctx.request.post(BASE+'/api/auth/login',{headers:{'X-Requested-With':'timelog'},data:{username:user,password:'qa-system-password-1'}});assert.equal(login.status(),200);
 if(user==='qa_alice'){
  const tasks=await (await ctx.request.get(BASE+'/api/tasks')).json();
  for(const task of tasks.filter(t=>t.status==='running'))await ctx.request.post(BASE+`/api/tasks/${task.id}/stop`,{headers:{'X-Requested-With':'timelog'}});
  const created=await ctx.request.post(BASE+'/api/tasks',{headers:{'X-Requested-With':'timelog'},data:{title:'تسک مکث‌شده برای ممیزی دسترس‌پذیری'}});assert.equal(created.status(),201);const task=await created.json();
  const paused=await ctx.request.post(BASE+`/api/tasks/${task.id}/pause`,{headers:{'X-Requested-With':'timelog'}});assert.equal(paused.status(),200);
 }
 const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});
 const widths=user==='qa_admin'?[360,1440]:[320,360,390,768,1024,1440,1920];
 for(const theme of ['light','dark','system']){
  await page.evaluate(v=>localStorage.setItem('timelog-theme',v),theme);
  await page.emulateMedia({colorScheme:theme==='light'?'light':'dark'});
  for(const width of widths){await page.setViewportSize({width,height:900});
   for(const route of ['/','/planned/','/dashboard/','/calendar/','/timesheet/','/tasks/','/daylog/','/settings/','/admin/']){
    await test(`${user} ${theme} ${width} ${route}`,async()=>{
     await page.goto(BASE+route);await page.locator('main').waitFor();await page.waitForLoadState('networkidle',{timeout:15000});
     await page.waitForFunction(()=>document.querySelector('main')?.textContent.trim().length>20);
     await page.waitForFunction(v=>document.documentElement.dataset.theme===v,theme==='light'?'light':'dark');
     const state=await page.evaluate(()=>({rtl:document.documentElement.dir,width:innerWidth,scroll:document.documentElement.scrollWidth,buttons:[...document.querySelectorAll('button,input,select,textarea')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height;}).filter(e=>{const r=e.getBoundingClientRect();return !e.closest('.ts-wrap, .table-scroll')&&(r.left < -1||r.right>innerWidth+1);}).map(e=>e.getAttribute('aria-label')||e.textContent.slice(0,80))}));
     assert.equal(state.rtl,'rtl');assert.ok(state.scroll<=state.width+1,JSON.stringify(state));assert.deepEqual(state.buttons,[]);
     if(user==='qa_alice'&&[320,1440].includes(width)&&['/','/settings/','/admin/'].includes(route)&&theme!=='system')await page.screenshot({path:path.join(OUT,`${theme}-${width}-${route==='/'?'today':route.split('/')[1]}.png`),fullPage:true});
    });
    if([390,1440].includes(width))await test(`Accessibility ${user} ${theme} ${width} ${route}`,async()=>{
     await page.addScriptTag({content:axe});
     const findings=await page.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));});
     assert.deepEqual(findings,[]);
    });
   }
  }
 }
 if(user==='qa_alice')for(const desktopWidth of [1440,1920])await test(`Desktop uses monitor space ${desktopWidth}`,async()=>{
  await page.setViewportSize({width:desktopWidth,height:1000});await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});await page.locator('.today-workspace').waitFor();
  const box=await page.locator('main').boundingBox();assert.ok(box.width>=(desktopWidth===1920?1200:900));
  const columns=await page.locator('.today-workspace').evaluate(e=>getComputedStyle(e).gridTemplateColumns.trim().split(/\s+/).length);assert.equal(columns,2);
 });
 if(user==='qa_alice')await test('Mobile timesheet scroll reveals final day control',async()=>{
  await page.setViewportSize({width:320,height:800});await page.goto(BASE+'/timesheet/');const last=page.locator('.ts-day-btn').last();await last.scrollIntoViewIfNeeded();const box=await last.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=321);await last.click();await page.waitForURL(BASE+'/daylog/');
 });
 if(user==='qa_admin')await test('Mobile user table scroll exposes account controls',async()=>{
  await page.setViewportSize({width:360,height:800});await page.goto(BASE+'/admin/');const control=page.locator('.user-table button').last();await control.scrollIntoViewIfNeeded();const box=await control.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=361);
 });
 await test(`${user} theme toggle persists`,async()=>{await page.goto(BASE+'/settings/');await page.getByRole('button',{name:'روشن',exact:true}).click();await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');});
 await test(`${user} keyboard navigation visible focus`,async()=>{await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});await page.getByRole('heading',{name:'TIME LOG',exact:true}).waitFor();await page.locator('.skip-link').waitFor({state:'attached'});await page.keyboard.press('Tab');const state=await page.evaluate(()=>({tag:document.activeElement.tagName,visible:document.activeElement.getBoundingClientRect().width>0}));assert.notEqual(state.tag,'BODY');assert.ok(state.visible);});
 if(user==='qa_alice')await test(`${user} dialog keyboard focus trap and Escape`,async()=>{
  await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});await page.locator('.card-done .task-row .task-title').first().click();const dialog=page.getByRole('dialog');await dialog.waitFor();
  assert.ok(await dialog.evaluate(e=>e.contains(document.activeElement)));
  for(let n=0;n<30;n++){await page.keyboard.press('Tab');assert.ok(await dialog.evaluate(e=>e.contains(document.activeElement)));}
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
 });
 if(user==='qa_alice')for(const modalTheme of ['light','dark'])for(const modalWidth of [320,1440])await test(`Task dialog accessibility ${modalTheme} ${modalWidth}`,async()=>{
  await page.setViewportSize({width:modalWidth,height:900});await page.evaluate(v=>localStorage.setItem('timelog-theme',v),modalTheme);await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});
  await page.locator('.card-done .task-row .task-title').first().click();const dialog=page.getByRole('dialog');await dialog.waitFor();await page.addScriptTag({content:axe});
  const findings=await page.evaluate(async()=>{const r=await axe.run(document.querySelector('[role=dialog]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));});
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});assert.deepEqual(findings,[]);
 });
 if(user==='qa_alice')await test('Keyboard menu returns focus after editing or cancelling deletion',async()=>{
  await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});const trigger=page.locator('.card-done .task-row').first().getByRole('button',{name:'گزینه‌های بیشتر',exact:true});
  await trigger.focus();await trigger.press('Enter');await page.getByRole('menu').waitFor();await page.keyboard.press('End');await page.keyboard.press('Home');await page.getByRole('menuitem',{name:'ویرایش ✎',exact:true}).click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});assert.ok(await trigger.evaluate(e=>e===document.activeElement));
  await trigger.press('Enter');await page.getByRole('menuitem',{name:'حذف 🗑',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'انصراف',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});assert.ok(await trigger.evaluate(e=>e===document.activeElement));
  await trigger.click();await page.getByRole('menu').waitFor();await trigger.click();await page.getByRole('menu').waitFor({state:'hidden'});
  await trigger.focus();await trigger.press('Enter');await page.getByRole('menu').waitFor();await page.keyboard.press('Tab');await page.getByRole('menu').waitFor({state:'hidden'});
 });
 if(user==='qa_alice')await test('Deleting a task from its keyboard menu returns focus to main',async()=>{
  const created=await ctx.request.post(BASE+'/api/tasks',{headers:{'X-Requested-With':'timelog'},data:{title:'حذف با صفحه‌کلید QA',start_time:'01:13',end_time:'01:14'}});assert.equal(created.status(),201);const task=await created.json();
  await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});const row=page.locator('.task-row').filter({hasText:'حذف با صفحه‌کلید QA'});const trigger=row.getByRole('button',{name:'گزینه‌های بیشتر',exact:true});await trigger.focus();await trigger.press('Enter');await page.getByRole('menuitem',{name:'حذف 🗑',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'بله، حذف کن',exact:true}).click();await row.waitFor({state:'hidden'});await page.waitForFunction(()=>document.activeElement===document.querySelector('main'));
  const tasks=await (await ctx.request.get(BASE+'/api/tasks')).json();assert.ok(!tasks.some(t=>t.id===task.id));
 });
 if(user==='qa_alice')await test('Network failure preserves task draft and permits retry',async()=>{
  await page.goto(BASE+'/');await page.waitForLoadState('networkidle',{timeout:15000});const input=page.getByLabel('شرح فعالیت',{exact:true});const draft='پیش‌نویس محفوظ هنگام قطع شبکه '+Date.now();await input.fill(draft);
  await page.route('**/api/tasks',r=>r.request().method()==='POST'?r.abort('failed'):r.continue());
  await page.getByRole('button',{name:'ثبت تسک ▶',exact:true}).click();await page.waitForTimeout(500);assert.equal(await input.inputValue(),draft);
  await page.unroute('**/api/tasks');await page.getByRole('button',{name:'ثبت تسک ▶',exact:true}).click();await page.waitForFunction(el=>el.value==='',await input.elementHandle());
  const tasks=await (await ctx.request.get(BASE+'/api/tasks')).json();assert.equal(tasks.filter(t=>t.title===draft).length,1);
 });
 await ctx.close();
}
await test('No uncaught JavaScript errors',()=>assert.deepEqual(errors,[]));
}finally{await browser.close();fs.writeFileSync(path.join(OUT,'ui.json'),JSON.stringify({results,errors},null,2));console.log(JSON.stringify({passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').length}));if(results.some(r=>r.status==='failed'))process.exitCode=1;}
})().catch(e=>{console.error(e);process.exitCode=1;});
