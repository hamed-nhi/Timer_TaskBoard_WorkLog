const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const BASE=process.env.QA_BASE_URL||'http://localhost:18083';
if(!/^http:\/\/(localhost|127\.0\.0\.1):1808[23]$/.test(BASE))throw Error('Isolated local target required');
if(!process.env.QA_ASSET_USER||!process.env.QA_ASSET_PASSWORD)throw Error('Disposable test credentials required in environment');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});const context=await browser.newContext();const external=[];const pages=[];
try{await context.route('**/*',route=>{const u=new URL(route.request().url());if(/^https?:$/.test(u.protocol)&&u.origin!==BASE){external.push(u.origin);return route.abort();}return route.continue();});
const page=await context.newPage();await page.goto(BASE+'/login/');await page.getByLabel('نام کاربری',{exact:true}).fill(process.env.QA_ASSET_USER);await page.getByLabel('رمز عبور',{exact:true}).fill(process.env.QA_ASSET_PASSWORD);await page.getByRole('button',{name:'ورود',exact:true}).click();await page.waitForURL(BASE+'/');
for(const route of ['/','/planned/','/tasks/','/daylog/','/dashboard/','/calendar/','/timesheet/','/settings/','/admin/']){await page.goto(BASE+route);await page.waitForLoadState('networkidle');await page.evaluate(()=>document.fonts.ready);assert.equal(await page.locator('body').innerText().then(x=>x.includes('404')),false);pages.push(route);}
assert.deepEqual(external,[]);const fonts=await page.evaluate(()=>performance.getEntriesByType('resource').filter(r=>/\.woff2?/.test(r.name)).map(r=>new URL(r.name).origin));assert.ok(fonts.length>0);assert.ok(fonts.every(origin=>origin===BASE));
fs.writeFileSync('artifacts/audit/local-assets.json',JSON.stringify({pages,externalRequests:external,localFontResources:fonts.length,status:'passed'},null,2));console.log(JSON.stringify({pages:pages.length,externalRequests:external.length,localFonts:fonts.length}));
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exit(1)});
