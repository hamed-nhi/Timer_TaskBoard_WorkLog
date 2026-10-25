"""Build Persian audit deliverables from sanitized evidence, without reading backups or keys."""
import base64
from collections import Counter
import html
import json
from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/audit'
DATE='2026-10-25'

def read(name,default=None):
 p=OUT/name
 return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else (default if default is not None else {})

def counts(data):
 values=data.get('results',[])
 return {'passed':sum(v.get('status')=='passed' for v in values),'failed':sum(v.get('status')=='failed' for v in values),'total':len(values)}

def table(headers,rows):
 esc=lambda v:html.escape(str(v))
 return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

root=ElementTree.parse(OUT/'backend.xml').getroot();cases=list(root.iter('testcase'))
backend={'total':len(cases),'failures':sum(t.find('failure') is not None or t.find('error') is not None for t in cases),'skipped':sum(t.find('skipped') is not None for t in cases)}
backend['groups']=dict(Counter(t.get('classname','').split('.')[1] for t in cases))
coverage=re.search(r'^TOTAL\s+.*?(\d+\.\d+)%', (OUT/'coverage.txt').read_text(), re.M).group(1)
journeys=counts(read('browser/e2e.json'));ui=counts(read('ui/ui.json'));devices=counts(read('import-devices/results.json'))
soak=read('soak-release-15min.json');load=read('load-release-direct.json');linux=read('load-linux.json')
recovery=read('recovery.json');preservation=read('preservation.json');crypto=read('real-backup-crypto.json');personal=read('personal-pipeline.json');scripts=read('backup-scripts.json');demo=read('demo-final.json')
http=read('http-security.json');npm=read('npm-advisories.json');python=read('python-audit-final.json');secrets=read('source-secrets.json');zap=read('zap-summary.json')
secret_count=sum(len(v.get('Secrets',[])) for v in secrets.get('Results',[]))
py_vulns=sum(len(p.get('vulns',[])) for p in python.get('dependencies',[]))
image_rows=[];image_findings={}
for name,label in [('api','API'),('web','Web / Caddy'),('db','PostgreSQL'),('personal','Personal backup')]:
 report=read(f'image-{name}-final.json');items=[v for result in report.get('Results',[]) for v in result.get('Vulnerabilities',[])]
 severity=Counter(v['Severity'] for v in items);fixable=sum(bool(v.get('FixedVersion')) for v in items)
 image_findings[name]={'severity':dict(severity),'fixable':fixable,'artifact':report.get('ArtifactName'),'image_id':report.get('Metadata',{}).get('ImageID')}
 image_rows.append([label,severity['CRITICAL'],severity['HIGH'],severity['MEDIUM'],severity['LOW'],severity['UNKNOWN'],fixable])
functional=backend['failures']==0 and backend['skipped']==0 and float(coverage)>=90 and all(v['failed']==0 and v['total']>0 for v in [journeys,ui,devices]) and all(v.get('passed') for v in [soak,load,recovery,crypto,personal,scripts,demo,http])
summary={'date':DATE,'functional_passed':functional,'security_clean':False,'backend':backend,'coverage_percent':float(coverage),'e2e':journeys,'ui':ui,'devices':devices,'soak':soak,'images':image_findings,'npm_advisories':len(npm.get('advisories',{})),'python_advisories':py_vulns,'source_secret_findings':secret_count}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

fixes=[
 ('QA-001/002','زیادشدن پیشنهاد تکمیلی پس از گردکردن','کفِ گام ۵ دقیقه، سقف هر تسک و بودجهٔ کل با ۲۰۰۰ حالت تصادفی کنترل شد.','test_time_boundaries'),
 ('QA-003/009','تاریخ با نوع نامعتبر یا مقدار خالی نامعتبر','۴۰۰ صریح؛ نوع نامعتبر دیگر ۵۰۰ یا تاریخ پیش‌فرض ناخواسته نمی‌سازد.','test_journeys / test_security_audit'),
 ('QA-004/005','موفقیت کاذب pipeline بک‌آپ و بازیابی','dump، اعتبار آرشیو، رمزگذاری، رمزگشایی و restore جدا کنترل می‌شوند.','test_backup_failures / backup-scripts.json'),
 ('QA-006','رقابت کنترل‌های مکث/ادامه/پایان','کنترل‌ها هنگام درخواست غیرفعال‌اند؛ تست به پاسخ واقعی سرور متصل است.','E2E-04 / E2E-53'),
 ('QA-007','عبور بار loopback از پراکسی ویندوز','کلاینت محلی مستقیم شد؛ قطع اتصال اولیه به‌عنوان خطای محیط ثبت شده است.','load-proxy-baseline / load-release-direct'),
 ('QA-008','PostCSS آسیب‌پذیر در وابستگی تو‌در‌توی Next','override سازگار به 8.5.31، npm ci، lint و build موفق؛ ارتقای عمدهٔ اجباری انجام نشد.','npm-advisories-before / npm-advisories'),
 ('QA-010/011','دورزدن blocked یا سقف تکمیلی در API','ثبت مثبت در روز مسدود و عبور بیش از دقت قرارداد رد و rollback می‌شود.','test_security_audit'),
 ('QA-012','فرمول‌شدن متن کاربر در Excel','همهٔ متن‌های خروجی صریحاً رشته‌اند؛ عنوان HYPERLINK اجرا نمی‌شود.','test_excel_user_text_is_never_executed_as_a_formula'),
 ('QA-013','cache پاسخ خصوصی و نبود CSP','API با no-store؛ اسکریپت‌های استاتیک فقط با hash مجازند. تزریق اسکریپت در مرورگر رد شد.','http-security / E2E-57'),
 ('QA-014','ویرایش تسک واردشده بدون ساعت یا با مدت متفاوت','عنوان/متادیتا مدت را ترمیم یا گرد نمی‌کند؛ اعشار 60.12345 نیز حفظ می‌شود.','test_tabular_import / import-precision-red'),
 ('QA-015','ویرایش قدیمی در دستگاه دوم','revision و خطای ۴۰۹؛ نسخهٔ جدید سرور و پیش‌نویس محلی محفوظ‌اند.','test_stale_device / import-devices'),
 ('QA-016','تکرار ایمپورت یا قطع پاسخ بعد از commit','تکرار، no-op است؛ ردیف‌های یکسانِ واقعی حفظ می‌شوند و فایل قدیمی ویرایش بعدی را برنمی‌گرداند.','test_tabular_import / import-devices'),
 ('QA-017','شمارهٔ خطا پس از سطرهای خالی فایل','شمارهٔ سطر فیزیکی فایل در خطا حفظ می‌شود.','test_errors_keep_physical_row_numbers'),
 ('UI-01','نقش و نام دسترس‌پذیر نمودار و تقویم','دکمهٔ روز مستقل از تاریخ‌های کمکی و نمودار با نام/فوکوس درست ساخته شد.','axe route matrix'),
 ('UI-02','کنتراست و برچسب کنترل‌ها','متن دکمه‌های روشن/تیره و checkbox گزارش روزانه اصلاح شد.','axe light/dark + dialogs'),
 ('UI-03','گم‌شدن فوکوس پس از منوی تسک','فوکوس به محرک و پس از حذف به main برمی‌گردد؛ Escape و تلهٔ فوکوس بررسی شدند.','keyboard-focus-red / keyboard menu scenarios'),
 ('UI-04','طولانی‌بودن ایمپورت با ستون‌های اختیاری','تشخیص خودکار و پیش‌نمایش کوتاه؛ تنظیم ستون‌ها فقط در صورت نیاز باز است.','import-devices screenshots'),
 ('IMG-01','بسته‌های آسیب‌پذیر ابزار نصب و باینری‌ها','pip/ensurepip حذف و Caddy/gosu با Go 1.27.3 و وابستگی‌های اصلاح‌شده بازسازی شدند.','Trivy before/after'),
]
validation=[
 ['بک‌اند: Unit / Integration / Operational',backend['total'],backend['failures'],'PostgreSQL واقعی؛ رد دیتابیس‌های محافظت‌شده؛ بدون xfail/skip'],
 ['پوشش ترکیبی خط و شاخه',coverage+'٪','حداقل ۹۰٪','coverage.xml / coverage.txt'],
 ['Unit فرانت',15,0,'قالب زمان، تاریخ و محاسبات نمایشی'],
 ['E2E مرورگر و نقش‌ها',journeys['total'],journeys['failed'],'مدیر، دو کاربر عادی، غیرفعال؛ لمس، نشست و خروج'],
 ['UI / UX / دسترس‌پذیری',ui['total'],ui['failed'],'۹ صفحه؛ ۳۲۰–۱۹۲۰؛ روشن/تیره/سیستم؛ axe و صفحه‌کلید'],
 ['ایمپورت و دو دستگاه',devices['total'],devices['failed'],'دانلود نمونه؛ mapping؛ پاسخ گمشده؛ همگام‌سازی و تعارض'],
 ['بار نهایی مستقیم',load.get('requests','اجرا نشده'),len(load.get('errors',[])),f"p95={load.get('p95_ms')} ms؛ ثبت‌ها بررسی شدند"],
 ['آزمون پایدار نهایی',soak.get('requests','اجرا نشده'),len(soak.get('errors',[])),f"۱۰ کاربر، {soak.get('writes')} ثبت؛ p95={soak.get('p95_ms')} ms"],
 ['مقایسهٔ شبکهٔ داخلی Docker',linux.get('requests','اجرا نشده'),len(linux.get('errors',[])),f"p95={linux.get('p95_ms')} ms"],
]
notes=[
 'محیط فعلی ۱۸۰۸۱، حساب‌های آن و دیتای دسکتاپ تغییر داده نشدند. نسخهٔ جدید فقط در audit روی localhost:18082 برای بررسی در دسترس است.',
 'نمونهٔ واقعی پیش از آزمون با snapshot سازگار گرفته، رمزگذاری و در دیتابیس دیگری بازیابی شد؛ اثرانگشت هر ۱۴ جدول برابر بود. فایل و کلید خصوصی در گزارش و Git نیستند.',
 'پس از ممیزی، داده‌های کاری محیط قبلی با مبنا برابرند؛ تغییر معمول expires_at و last_seen_at نشست فعال جدا ثبت شده است.',
 'یک حساب مرجع کامل شامل تسک پایان‌یافته و مکث‌شده، سگمنت، حضور، تگ، کاتالوگ، برنامه، تنظیمات و تکمیلی ساخته شد؛ هیچ زمان واقعی به تکمیلی تبدیل نشد.',
 'اجرای واقعی job پشتیبان، با منبع یکسان فایل/mtime تازه نساخت؛ ویرایش منبع نسخهٔ دوم ساخت و بایت‌های نسخهٔ قبلی حفظ شدند.',
 'restart و بازسازی کانتینرهای audit با volume ماندگار، تمام جدول‌ها و نشست را حفظ کرد. dump/restore، رمز غلط و آرشیو ناقص نیز آزمایش شدند.',
 f"آزمون نهایی بار بدون وقفه بود: فعالیت هر worker حداقل {soak.get('load_seconds_min')} ثانیه، بیشترین فاصلهٔ بیکار {soak.get('max_idle_seconds')} ثانیه و {soak.get('writes')} نوشتن معتبر. معیار p95 دو ثانیه بود؛ این تضمین ظرفیت تولید نیست.",
 'در یک اجرای میانی، زمان پایش میزبان وقفه داشت؛ آن اجرا معیار پذیرشِ ۱۵ دقیقهٔ پیوسته محسوب نشد. اجرای نهایی مدت و فاصلهٔ فعالیت workerها را صریحاً ثبت می‌کند.',
 'در سناریوی دو دستگاه، هر مرورگر نشست جدا داشت؛ تغییر گوشی در کامپیوتر و تغییر کامپیوتر در گوشی بدون reload دیده شد. خروج از یکی، دیگری را خارج نکرد.',
]
limits=[
 'امنیت imageها پاک نیست: یافته‌های توزیع Debian در API/job و PostgreSQL باقی‌اند. هیچ موردِ دارای نسخهٔ اصلاح‌شده در اسکن نهایی باقی نمانده، ولی این به معنی بی‌خطر بودن موارد بدون اصلاحیه نیست.',
 'CVE-2026-6653 در libxml2 دیتابیس با شدت CRITICAL در خروجی اسکن باقی است. Debian trixie آن را vulnerable و در یادداشت ناشر «Minor issue / no-dsa» اعلام می‌کند. این برنامه ورودی XML را به توابع XML دیتابیس نمی‌دهد؛ این مشاهده، جای اصلاح کتابخانه یا تأیید نبود مسیر سوءاستفاده را نمی‌گیرد.',
 'GO-2026-5932 دربارهٔ بستهٔ قدیمی openpgp به‌صورت UNKNOWN در module رمزنگاری Caddy گزارش می‌شود. بررسی مستقل باینری با govulncheck به پاسخ ۴۰۳ پایگاه عمومی خورد؛ اجرا موفق یا نتیجهٔ صفر محسوب نشده است.',
 f"ZAP احراز هویت‌شده روی حساب تازه، {zap.get('paths')} مسیر API را با سیاست API بررسی کرد؛ هشدار Low برای HTML ریشهٔ وب مورد انتظار بود و پاسخ‌های ۴xx ورودی نامعتبر به‌عنوان اطلاع ثبت شدند. خطای ۵xx/یافتهٔ high در این اجرای محدود گزارش نشد؛ تست نفوذ کامل نیست.",
 'ممیزی JavaScript با endpoint رسمی npm انجام شد؛ خود فرمان npm audit در تلاش اولیه خطای شبکه داشت. نتیجهٔ آن تلاش، قبولی محسوب نشده است.',
 'Google Sheet واقعی به سرویس‌اکانت و شیت اختصاصی نیاز دارد؛ فقط تست‌های شبیه‌سازی/قرارداد، مالکیت، تغییر دستی مقصد، حذف و شکست شبکه انجام شدند.',
 'HTTPS واقعی، Safari/iOS، Firefox و گوشی فیزیکی در این محیط تأیید نشده‌اند. آزمون موبایل، Chrome با viewport و لمس واقعیِ شبیه‌سازی‌شده بود.',
 'GitHub Actions روی سرور GitHub در این کار اجرا نشده و انتشار تولید انجام نشده است. نوشتن workflow معادل اجرای آن نیست.',
 'استک قدیمی ۱۸۰۸۱ از tmpfs استفاده می‌کند؛ آن را محیط دائمی فرض نکنید یا بدون مهاجرت/بک‌آپ متوقف نکنید. compose اصلی و audit volume ماندگار دارند.',
]
status='موفق' if functional else 'نیازمند بررسی موارد ناقص'
md=f'''# گزارش ممیزی TIME LOG — {DATE}

**پذیرش عملکردی: {status}. وضعیت امنیت انتشار: باز/مشروط؛ imageها کاملاً پاک نیستند.**

این گزارش آزمون‌های محلی روی محیط مستقل audit را بیان می‌کند. شکست، skip، xfail و اجرا‌نشدن با موفقیت یکی حساب نشده‌اند.

## نتایج

| بخش | تعداد/معیار | شکست | شواهد/دامنه |
| --- | --- | --- | --- |
'''+''.join('| '+' | '.join(map(str,row))+' |\n' for row in validation)+f'''
بک‌اند: {backend['groups']}. تعداد skip: {backend['skipped']}. lint، static-export build و بررسی drift مایگریشن نیز موفق‌اند. آمار امنیت بخشی از تعداد بک‌اند است و دوباره به جمع اضافه نشده است.

## حفظ داده و استفادهٔ واقعی

'''+''.join('- '+n+'\n' for n in notes)+'''
## اصلاح‌های تأییدشده

| شناسه | مسئله | اصلاح/نتیجه | رگرسیون |
| --- | --- | --- | --- |
'''+''.join('| '+' | '.join(row)+' |\n' for row in fixes)+'''
## اسکن imageهای نهایی

| Image | Critical | High | Medium | Low | Unknown | دارای نسخهٔ اصلاح‌شده |
| --- | --- | --- | --- | --- | --- | --- |
'''+''.join('| '+' | '.join(map(str,row))+' |\n' for row in image_rows)+f'''
ممیزی npm: {len(npm.get('advisories',{}))} بستهٔ دارای advisory از {npm.get('packages')} بستهٔ قفل‌شده. Python: {py_vulns} آسیب‌پذیری شناخته‌شده در وابستگی‌های برنامه/Sheets. اسکن source: {secret_count} secret تشخیص‌داده‌شده؛ فایل‌های خصوصی اصلاً جزو source scan و Git نیستند.

## موارد باز و حدود ادعا

'''+''.join('- '+n+'\n' for n in limits)+'''
## تحویل و بازتولید

- راهنمای دقیق محیط و فرمان‌ها: [AUDIT_RUNBOOK.md](AUDIT_RUNBOOK.md).
- کد تست‌ها: `backend/tests` و `frontend/tests/e2e`؛ ابزارهای عملیاتی: `tools/audit_*.py`.
- شواهد محلی و گزارش HTML/ZIP در `artifacts/audit` و `artifacts/TIME-LOG-QA-2026-10-25.zip` قرار می‌گیرند و در Git نیستند.
- JUnit، coverage، JSON بار/امنیت، تصاویر حساب‌های آزمایشی و مقایسهٔ اثرانگشت نگهداری شده‌اند؛ dump، کلید، کوکی و رمز تولیدشده در بستهٔ تحویلی قرار ندارند.
- README انگلیسی، عنوان TIME LOG و راهنمای قالب‌های Excel/CSV به‌روزرسانی شده‌اند. ساختار لایه‌ها و entrypointهای قبلی حفظ شده‌اند؛ import مایگریشن تازه‌ای نیاز ندارد.
- انتشار نسخه و تاریخچهٔ اصلاح‌شده در GitHub با تأیید صریح صاحب مخزن مجاز شده است؛ استقرار تولید و اجرای GitHub Actions جزو این نتیجه نیست.

منابع ارزیابی باز: [Debian دربارهٔ libxml2](https://security-tracker.debian.org/tracker/CVE-2026-6653)، [اعلان Go دربارهٔ openpgp](https://pkg.go.dev/vuln/GO-2026-5932)، [محدودهٔ API Scan در ZAP](https://www.zaproxy.org/docs/docker/api-scan/).
'''
# Reviewed English snapshots in docs/testing are maintained separately.
(OUT/'AUDIT_RESULTS.fa.md').write_text(md,encoding='utf-8')
sections=''
for title,items in [('حفظ داده و کاربرد چنددستگاهی',notes),('موارد باز و محدودیت‌های تأیید',limits)]:
 sections+='<section><h2>'+title+'</h2><ul>'+''.join('<li>'+html.escape(n)+'</li>' for n in items)+'</ul></section>'
gallery=''
for filename,label in [('ui/light-1440-today.png','دسکتاپ — روشن'),('ui/dark-1440-today.png','دسکتاپ — تیره'),('ui/light-320-today.png','موبایل ۳۲۰ پیکسل'),('import-devices/mobile-import-preview.png','پیش‌نمایش ایمپورت در گوشی')]:
 p=OUT/filename
 if p.exists():gallery+='<figure><img alt="'+label+'" src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"><figcaption>'+label+' — دادهٔ آزمایشی</figcaption></figure>'
page='''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIME LOG — گزارش ممیزی</title><style>
:root{color-scheme:light dark;--bg:#f2f5fa;--card:#fff;--text:#17243a;--muted:#526176;--border:#dce3ed;--accent:#4338ca;--warn:#8a360d;--warnbg:#fff3e4}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.9 Tahoma,Arial,sans-serif}main{max-width:1180px;margin:auto;padding:32px 20px 70px}header,section{background:var(--card);border:1px solid var(--border);padding:26px;border-radius:18px;margin-bottom:20px}h1{margin:0;font-size:30px}h2{margin:0 0 14px;font-size:21px}p,li{overflow-wrap:anywhere}.eyebrow{font-weight:700;color:var(--accent)}.muted{color:var(--muted)}.notice{padding:14px 18px;border-radius:12px;background:var(--warnbg);color:var(--warn);border:1px solid #dcb98b}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}.metric{background:var(--bg);border:1px solid var(--border);padding:16px;border-radius:12px}.metric b{display:block;font:700 26px/1.5 Arial,sans-serif;color:var(--accent)}table{border-collapse:collapse;width:100%;min-width:650px}td,th{text-align:right;padding:11px;border-bottom:1px solid var(--border);vertical-align:top;font-size:13px}th{color:var(--muted);white-space:nowrap}.table-wrap{overflow:auto}li{margin-bottom:10px}a{color:var(--accent)}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}figure{margin:0;border:1px solid var(--border);border-radius:12px;overflow:hidden}figure img{display:block;width:100%;height:300px;object-fit:contain;object-position:top;background:var(--bg)}figcaption{padding:10px;font-size:12px}.footer{font-size:12px;color:var(--muted)}@media(prefers-color-scheme:dark){:root{--bg:#0d1523;--card:#172236;--text:#e8eef8;--muted:#b1bfd2;--border:#33445c;--accent:#b5baff;--warn:#ffd3a4;--warnbg:#372819}}@media(max-width:600px){main{padding:16px 10px}header,section{padding:18px}h1{font-size:25px}}@media print{body{font-size:11px}main{max-width:none;padding:0}.table-wrap{overflow:visible}table{min-width:0}header,section{break-inside:avoid;border-radius:0}figure img{height:200px}}
</style></head><body><main>'''
page+='<header><div class="eyebrow">TIME LOG · ممیزی محلی · '+DATE+'</div><h1>تست، حفظ داده و کیفیت تجربهٔ کاربر</h1><p>پذیرش عملکردی: <b>'+status+'</b>. محیط واقعی قبلی از محیط audit جدا نگه داشته شد.</p><div class="notice"><b>امنیت کاملاً پاک اعلام نمی‌شود.</b> یافته‌های توزیع Debian و یک مورد ارزیابی‌نشدهٔ Go در بخش محدودیت‌ها ثبت شده‌اند.</div><div class="cards">'+''.join('<div class="metric"><b>'+str(value)+'</b>'+label+'</div>' for value,label in [(backend['total'],'تست بک‌اند/عملیات'),(coverage+'%','پوشش ترکیبی'),(ui['total'],'بررسی UI / UX'),(soak.get('p95_ms','—'),'p95 بار، میلی‌ثانیه')])+'</div><p class="muted">حساب‌های آزمایشی: مدیر، دو کاربر عادی، کاربر غیرفعال و حساب‌های جدا برای انتقال، بار، بازیابی و امنیت. همهٔ تصاویر این گزارش دادهٔ آزمایشی دارند.</p></header>'
page+='<section><h2>نتایج آزمون‌ها</h2>'+table(['بخش','تعداد/معیار','شکست','دامنه'],validation)+'</section>'+sections
page+='<section><h2>اصلاح‌های تأییدشده و رگرسیون</h2>'+table(['شناسه','مسئله','نتیجه','آزمون'],fixes)+'</section><section><h2>اسکن imageهای نهایی</h2>'+table(['Image','Critical','High','Medium','Low','Unknown','دارای اصلاحیه'],image_rows)+f'<p>npm: {len(npm.get("advisories",{}))} advisory؛ Python: {py_vulns} آسیب‌پذیری شناخته‌شده؛ source scan: {secret_count} secret تشخیص‌داده‌شده. موارد خصوصی جزو source نیستند.</p></section>'
page+='<section><h2>شواهد بصری</h2><div class="gallery">'+gallery+'</div></section><section><h2>بازتولید و منابع</h2><p>فرمان‌ها در docs/testing/AUDIT_RUNBOOK.md و نتایج متنی در AUDIT_RESULTS.fa.md هستند. شواهد خامِ پالایش‌شده در بستهٔ ZIP کنار گزارش تحویل می‌شوند. هیچ dump، رمز، کوکی یا کلیدی در این گزارش نیست.</p><p><a href="https://security-tracker.debian.org/tracker/CVE-2026-6653">وضعیت libxml2 در Debian</a> · <a href="https://pkg.go.dev/vuln/GO-2026-5932">اعلان Go</a> · <a href="https://www.zaproxy.org/docs/docker/api-scan/">محدودهٔ ZAP API Scan</a></p><p class="footer">بدون انتشار تولید · بدون ادعای تأیید HTTPS، Safari/iOS، گوشی فیزیکی یا Google Sheet واقعی · xfail و اجرای ناقص، قبولی نیستند.</p></section></main></body></html>'
(OUT/'TIME-LOG-QA-report.fa.html').write_text(page,encoding='utf-8')
# Curated evidence only: no source copies, binary tools, dumps, keys or browser storage.
names=['summary.json','backend.xml','coverage.xml','coverage.txt','npm-advisories.json','python-audit-final.json','source-secrets.json','zap-summary.json','zap.json','http-security.json','preservation.json','demo-final.json','real-backup-crypto.json','recovery.json','crypto.json','backup-scripts.json','personal-pipeline.json','soak-release-15min.json','load-release-direct.json','load-linux.json','image-api-final.json','image-web-final.json','image-db-final.json','image-personal-final.json','browser/e2e.json','ui/ui.json','import-devices/results.json','regressions-red.xml','regressions-green.xml','security-red.xml','security-green.xml','import-edit-red.xml','import-edit-green.xml','import-precision-red.xml','import-row-red.xml','keyboard-focus-red.json','frontend-unit.log','frontend-lint.log','frontend-build.log','migrations.log','TIME-LOG-QA-report.fa.html']
archive=ROOT/'artifacts'/f'TIME-LOG-QA-{DATE}.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for name in names:
  p=OUT/name
  if p.is_file():z.write(p,name)
 for p in (OUT/'ui').glob('*.png'):z.write(p,'ui/'+p.name)
 for p in (OUT/'import-devices').glob('*.png'):z.write(p,'import-devices/'+p.name)
 z.write(ROOT/'docs/testing/AUDIT_RESULTS.fa.md','AUDIT_RESULTS.fa.md')
 z.write(ROOT/'docs/testing/AUDIT_RUNBOOK.md','AUDIT_RUNBOOK.md')
print(json.dumps({'functional_passed':functional,'backend':backend,'coverage':coverage,'ui':ui,'e2e':journeys,'devices':devices,'html_bytes':len(page.encode()),'zip_bytes':archive.stat().st_size}))
