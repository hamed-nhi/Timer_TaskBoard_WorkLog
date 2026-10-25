/* Password visibility is presentation-only: no accidental submit, value loss or persistence. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const BASE=process.env.QA_BASE_URL||'http://127.0.0.1:18082';
if(!/^http:\/\/(localhost|127\.0\.0\.1):1808[23]$/.test(BASE))throw Error('Isolated local target required');
(async()=>{const browser=await chromium.launch({channel:process.env.QA_BROWSER_CHANNEL||'chrome',headless:true});const results=[];
try{for(const width of [320,390,1440])for(const theme of ['light','dark']){
 const context=await browser.newContext({viewport:{width,height:900},colorScheme:theme});const page=await context.newPage();let submits=0;
 await page.route('**/api/auth/login',route=>{submits++;assert.equal(route.request().postDataJSON().password,'Aa#12345');return route.fulfill({status:401,json:{error:'خطای ورود آزمایشی'}});});
 await page.goto(BASE+'/login/');const password=page.getByLabel('رمز عبور',{exact:true});await password.fill('Aa#12345');
 assert.equal(await password.getAttribute('type'),'password');
 const show=page.getByRole('button',{name:'نمایش رمز',exact:true});assert.equal(await show.innerText(),'');assert.equal(await show.locator('svg').getAttribute('width'),'20');assert.equal(await show.locator('line').count(),1);
 const inputBox=await password.boundingBox();const iconBox=await show.boundingBox();assert.ok(iconBox.x>=inputBox.x&&iconBox.x+iconBox.width<=inputBox.x+inputBox.width&&iconBox.y>=inputBox.y&&iconBox.y+iconBox.height<=inputBox.y+inputBox.height);
 assert.equal(await show.getAttribute('aria-pressed'),'false');await show.click();
 assert.equal(await password.getAttribute('type'),'text');assert.equal(await page.locator('.password-visibility-toggle line').count(),0);assert.equal(await password.inputValue(),'Aa#12345');
 const hide=page.getByRole('button',{name:'پنهان‌کردن رمز',exact:true});assert.equal(await hide.getAttribute('aria-pressed'),'true');await hide.press('Enter');
 assert.equal(await password.getAttribute('type'),'password');assert.equal(submits,0);
 await page.getByLabel('نام کاربری',{exact:true}).fill('qa_visibility');await page.getByRole('button',{name:'نمایش رمز',exact:true}).click();
 await page.getByRole('button',{name:'ورود',exact:true}).click();await page.getByRole('alert').filter({hasText:'خطای ورود آزمایشی'}).waitFor();
 assert.equal(submits,1);assert.equal(await password.getAttribute('type'),'password');assert.equal(await password.inputValue(),'Aa#12345');
 assert.equal(await page.evaluate(()=>Object.values(localStorage).some(v=>v.includes('Aa#12345'))||Object.values(sessionStorage).some(v=>v.includes('Aa#12345'))),false);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:path.resolve(__dirname,`../../../artifacts/audit/password-eye-${width}-${theme}.png`)});
 await context.close();results.push({width,theme,status:'passed'});
}}finally{await browser.close();const out=path.resolve(__dirname,'../../../artifacts/audit/password-visibility.json');fs.writeFileSync(out,JSON.stringify({results},null,2));}
console.log(JSON.stringify({passed:results.length}));})().catch(e=>{console.error(e.message);process.exit(1)});
