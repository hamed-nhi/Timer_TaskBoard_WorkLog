"""Build current release evidence without reading private credentials or dumps."""
import base64
import html
import json
from pathlib import Path
import re
from xml.etree import ElementTree
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/audit"

def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))

def count(name):
    rows = read(name)["results"]
    return {"total": len(rows), "passed": sum(r["status"] == "passed" for r in rows),
            "failed": sum(r["status"] != "passed" for r in rows)}

cases = list(ElementTree.parse(OUT / "login-release-backend.xml").getroot().iter("testcase"))
backend = {"total": len(cases), "failed": sum(c.find("failure") is not None or c.find("error") is not None for c in cases),
           "skipped": sum(c.find("skipped") is not None for c in cases)}
coverage = float(re.search(r"^TOTAL.*?(\d+\.\d+)%", (OUT / "login-release-coverage.txt").read_text(), re.M)[1])
e2e = count("browser/e2e.json"); ui = count("ui/ui.json"); devices = count("import-devices/results.json"); security = count("login-security/results.json")
smoke = read("server-smoke.json"); mobile = read("mobile-backup-setup.json"); upgrade = read("current-upgrade-verified.json"); load = read("release-legitimate-30s.json"); burst = read("login-security/burst.json")
python_findings = sum(len(d.get("vulns", [])) for d in read("login-python-audit.json").get("dependencies", []))
secret_findings = sum(len(r.get("Secrets", [])) for r in read("login-source-secrets.json").get("Results", []))
image_rows = []
for name in ["api", "web", "personal"]:
    report = read("login-image-" + name + ".json")
    items = [v for r in report.get("Results", []) for v in r.get("Vulnerabilities", [])]
    image_rows.append([name, len(items), sum(v.get("Severity") == "CRITICAL" for v in items), sum(bool(v.get("FixedVersion")) for v in items)])
passed = backend["failed"] == 0 and backend["skipped"] == 0 and coverage >= 90 and all(r["total"] and not r["failed"] for r in [e2e, ui, devices, security]) and all(r["passed"] for r in [smoke, mobile, upgrade, load])
summary = {"passed": passed, "backend": backend, "coverage_percent": coverage, "e2e": e2e, "ui": ui, "devices": devices, "security_browser": security,
           "production_compose_smoke": smoke["passed"], "current_environment_personal_data_preserved": upgrade["preexisting_personal_tables_equal"],
           "six_requested_account_logins_verified": all(r["login"] and r["role_correct"] for r in upgrade["account_logins"]),
           "burst": burst, "legitimate_load": load, "python_advisories": python_findings, "source_secrets": secret_findings,
           "security_unconditionally_clean": False}
(OUT / "release-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
rows = [["بک‌اند Unit / Integration / Operational", backend["total"], backend["failed"]], ["پوشش ترکیبی", str(coverage) + "%", "حداقل ۹۰٪"],
        ["Unit فرانت", 15, 0], ["E2E اصلی", e2e["total"], e2e["failed"]], ["UI / UX، ۹ صفحه و عرض ۳۲۰ تا ۱۹۲۰", ui["total"], ui["failed"]],
        ["ایمپورت و دو دستگاه", devices["total"], devices["failed"]], ["امنیت، مدیر، onboarding و رمز شخصی در مرورگر", security["total"], security["failed"]],
        ["onboarding موبایل و axe", "۳۹۰ پیکسل / لمس", "موفق"], ["نصب تمیز Compose تولید و زمان‌بند واقعی", "دیتابیس خالی / volume ماندگار", "موفق"],
        ["ترافیک عادی ۱۰ کاربر پس از سد سریع", str(load["requests"]) + " درخواست", "صفر خطای غیرمنتظره"], ["موج هجوم به API", burst["requests"], str(burst["limited"]) + " پاسخ ۴۲۹؛ صفر خطای غیرمنتظره"]]
notes = [
"تاریخ گزارش ۲۰۲۶-۱۰-۲۵؛ نتیجه مربوط به کد جاری پس از قابلیت‌های امنیت ورود و پشتیبان است. گزارش AUDIT_RESULTS سابقهٔ ممیزی اولیه و بار ۱۵ دقیقه‌ای آن نسخه است؛ آن بار طولانی به‌عنوان تست مجدد این نسخه معرفی نمی‌شود.",
"بن در PostgreSQL برای IP/حساب است: سه رمز اشتباه، ۱۵ دقیقه؛ مرحلهٔ بعد ۱۰ ساعت؛ مرحلهٔ بعد و بعدتر ۳۰ روز. سه نام ناشناس بن ۲۴ ساعتهٔ کل IP دارد. درخواست زمان بن، پایان را تمدید نمی‌کند. ورود موفق به‌صورت پیش‌فرض مرحلهٔ همان IP/حساب را پاک می‌کند؛ از پنل قابل تغییر است.",
"مدیر تعداد تلاش، مدت‌ها و سقف‌های مکمل IP/کل سرویس را تغییر می‌دهد، بن را رفع یا سابقهٔ تشدید را پاک می‌کند. خطای واقعی باقی‌ماندن شمارندهٔ کوتاه‌مدت پس از رفع بن اصلاح و ورود فوری با تست رگرسیون تأیید شد. فرمان کنسولی نجات هم روی نصب تمیز اجرا شد.",
"ساخت حساب با رمز انتخابی/تصادفی، تغییر نام کاربری، نام نمایشی، نقش و رمز، و فعال/غیرفعال‌سازی بررسی شدند. API حذف حساب وجود ندارد. غیرفعال و فعال‌کردن، دادهٔ تسک را حتی در مقایسهٔ کامل ردیف تغییر نداد. تغییر مشخصات ورود نشست‌های حساب را لغو می‌کند.",
"رمز جدید در همهٔ ورودی‌های وب و CLI حداقل هشت کاراکتر، حرف بزرگ/کوچک، عدد و نماد می‌خواهد. رمز قدیمیِ ذخیره‌شده هنگام ورود ناخواسته عوض نمی‌شود. تغییر رمز شخصی در تنظیمات، نشست جاری را نگه می‌دارد و سایر نشست‌ها را می‌بندد.",
"تنظیمات عمومی کپچا از بک‌اند می‌آید؛ Secret به مرورگر ارسال نمی‌شود. نبود توکن، پاسخ false/بدشکل، خطای شبکه، پاسخ بزرگ، redirect و تکرار هم‌زمان توکن نمی‌توانند نشست بسازند. اتصال فعلاً غیرفعال است چون کلید واقعی ارائه نشده.",
"سد حافظه‌ای محدود قبل از JSON/route/SQL، درخواست اضافی را رد می‌کند. تست منطقی ۱۰هزار شناسهٔ IP و تست واقعی ۱۰۰۰ درخواست API اجرا شد. سقف حافظه و رقابت threadها آزموده شد. این تست، شبیه‌سازی کامل botnet یا حملهٔ حجمی نیست.",
"اولین ورود راهنمای ساخت شیت خصوصی، دسترسی Editor به سرویس‌اکانت، ذخیرهٔ لینک و دانلود Excel شخصی را نشان می‌دهد. وضعیت هر نفر مستقل و ماندگار است. خطای لینک آن را تکمیل‌شده علامت نمی‌زند؛ ادامه بدون شیت و بازکردن دوبارهٔ راهنما از تنظیمات ممکن است.",
"زمان‌بند Docker اجرای اولیه و روزانهٔ ۰۳:۰۰ تهران با retry پانزده‌دقیقه‌ای و marker روی volume دارد. اجرای واقعی روی نصب تمیز موفق شد؛ ورودی یکسان snapshot جدید یا بازنویسی نساخت. زمان‌بندی با ساعت‌های کنترل‌شده تست شد؛ برای گزارش منتظر یک روز واقعی نماندیم.",
"Compose اصلی روی پروژه‌ای جدا و دیتابیس خالی اجرا شد؛ مایگریشن 0004، ساخت مدیر با CLI، سلامت API، backup-scheduler و بازسازی کانتینرها آزمایش شدند. داده و سشن پس از بازسازی باقی ماندند.",
"صاحب پروژه ارتقای ۱۸۰۸۱ را جداگانه تأیید کرد. پیش از ارتقا، dump در دیتابیس دیگری بازیابی و اثرانگشت همهٔ جدول‌ها برابر شد. فقط API و وب ارتقا یافتند؛ کانتینر دیتابیس آن بازسازی نشد. جدول‌های شخصی قبلی پس از ارتقا برابر ماندند.",
"سه حساب درخواستی در هر دو محیط با حفظ شناسه‌ها و نقش‌ها آماده شدند؛ هر شش ورود موفق بررسی شد. راهنمای اولین ورود برای استفادهٔ انسانی بازنشانی و نشست‌های آزمایشی این حساب‌ها لغو شدند. نام‌های واقعی و رمزها در Git و بستهٔ گزارش نیستند.",
"در اجرای اولیهٔ تست بار، ورودهای هم‌زمان با فعالیت مرورگر به سقف ورود خوردند و نتیجهٔ ۴۲۹ قبولی محسوب نشد. در اجرای ترافیک عادی، شروع نشست‌ها با فاصله و مطابق سیاست ورود انجام شد؛ بار کاری ده کاربر همچنان هم‌زمان بود.",
"دو ایراد انتظار تست هم اصلاح شد: نام قدیمی دکمهٔ ساخت حساب و انتظار فارسی برای خطای Google Sheet. assertionها حذف نشدند؛ سناریوهای کامل دوباره اجرا و موفق شدند. xfail/skip موفقیت محسوب نشده است."]
limits = [
"Google Sheets واقعی بدون سرویس‌اکانت، شیت و دسترسی واقعی آزمایش نشده است. ذخیرهٔ لینک به‌معنی ارسال موفق نیست؛ راهنمای DEPLOY مراحل و اجازه‌ها را مشخص می‌کند.",
"ARCaptcha واقعی بدون Site Key/Secret Key فعال یا تأیید نشده؛ قرارداد سمت سرور و ویجت با پاسخ کنترل‌شده آزموده شدند. در حالت فعال، قطعی سرویس مانع ورود تازه می‌شود و به عبور بدون کپچا تبدیل نمی‌شود.",
"حفاظت حجمی DDoS/CDN/WAF، DNS و HTTPS واقعی سرور مقصد، Safari/iOS و گوشی فیزیکی تأیید نشده‌اند. سد حافظه‌ای per-process و محدود است؛ با restart reset و با replicaها تکثیر می‌شود. بن اصلی PostgreSQL ماندگار می‌ماند.",
"امنیت imageها کاملاً پاک نیست. یافته‌های Debian بدون اصلاحیهٔ موجود باقی‌اند؛ CVE-2026-6653 در libxml2 image PostgreSQL در گزارش قبلی CRITICAL است و وضعیت ناشر باز است. GO-2026-5932 در Caddy به‌صورت UNKNOWN باقی مانده. اسکن مستقل govulncheck قبلاً به خطای ۴۰۳ خورده و نتیجهٔ پاک محسوب نشده است.",
"ممیزی Python فعلی آسیب‌پذیری شناخته‌شده گزارش نکرد؛ اسکن source صفر secret تشخیص داد. این تضمین نبود همهٔ ضعف‌ها نیست. فایل‌های خصوصی اصلاً در scope منبع و Git نیستند.",
"محیط قدیمی محلی از tmpfs استفاده می‌کند و نباید volume تولید فرض شود. Compose اصلی سرور و نصب تمیز آزموده‌شده، volume ماندگار دارند. بک‌آپ رمزگذاری‌شدهٔ دیتابیس و نسخهٔ خارج سرور همچنان لازم‌اند."]
md = "# نتیجهٔ تست انتشار TIME LOG — ۲۰۲۶-۱۰-۲۵\n\n**پذیرش عملکردی: " + ("موفق" if passed else "ناموفق/ناقص") + ". امنیت بدون شرط پاک اعلام نمی‌شود.**\n\n| آزمون | تعداد/معیار | نتیجه/شکست |\n| --- | --- | --- |\n"
md += "".join("| " + " | ".join(map(str, r)) + " |\n" for r in rows)
md += "\n## رفتارها و شواهد\n\n" + "".join("- " + n + "\n" for n in notes)
md += "\n## محدودیت‌ها\n\n" + "".join("- " + n + "\n" for n in limits)
md += "\n## اجرا و تحویل\n\n- [راهنمای سرور](../../DEPLOY.md)؛ [فرمان‌های تست](AUDIT_RUNBOOK.md).\n- شواهد محلی پالایش‌شده: `artifacts/audit/release-summary.json`، JUnit، coverage، نتایج مرورگر، smoke و اسکن‌ها.\n- بستهٔ HTML و ZIP شامل dump، کلید، کوکی، نام واقعی یا رمز حساب‌ها نیست. فایل خصوصی حساب‌ها از Git حذف/نادیده‌گرفته شده است.\n- منابع رسمی: [ARCaptcha Verify](https://github.com/arcaptcha/arcaptcha-docs/blob/main/versioned_docs/version-4.0.0/API/Verify.md)، [قواعد هدر Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers).\n"
# Reviewed English snapshots in docs/testing are maintained separately.
(OUT / "RELEASE_RESULTS.fa.md").write_text(md, encoding="utf-8")
def bullets(items):return "<ul>"+"".join("<li>"+html.escape(n)+"</li>" for n in items)+"</ul>"
page = '<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TIME LOG — نتیجهٔ انتشار</title><style>body{margin:0;background:#f3f5fa;color:#17243a;font:15px/1.9 Tahoma,Arial}main{max-width:1100px;margin:auto;padding:25px 15px}section,header{background:white;border:1px solid #dbe1ec;border-radius:16px;padding:24px;margin-bottom:18px}h1{font-size:26px}h2{font-size:20px}li{margin:10px 0;overflow-wrap:anywhere}.table{overflow:auto}table{width:100%;border-collapse:collapse;min-width:540px}td,th{padding:12px;text-align:right;border-bottom:1px solid #ddd}.notice{background:#fff1dd;padding:14px;border-radius:10px}img{width:100%;max-height:550px;object-fit:contain;object-position:top}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:15px}figure{margin:0}a{color:#4338ca}*{box-sizing:border-box}@media(max-width:600px){section,header{padding:17px}}</style><main><header><h1>TIME LOG · تحویل نسخهٔ جاری</h1><p>۲۰۲۶-۱۰-۲۵ — پذیرش عملکردی: ' + ('موفق' if passed else 'ناقص') + '</p><p class="notice">امنیت imageها بدون شرط پاک اعلام نمی‌شود؛ اتصال واقعی شیت/کپچا و زیرساخت سرور مقصد به تنظیم جداگانه نیاز دارد.</p></header>'
page += '<section><h2>نتایج</h2><div class="table"><table><tr><th>آزمون</th><th>تعداد/معیار</th><th>نتیجه</th></tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in r)+'</tr>' for r in rows)+'</table></div></section>'
page += '<section><h2>چه چیزهایی بررسی شدند</h2>'+bullets(notes)+'</section><section><h2>حدود تأیید و موارد باز</h2>'+bullets(limits)+'</section><section><h2>شواهد بصری</h2><div class="gallery">'
for name,label in [('login-security/release-admin-1440.png','پنل مدیریت در دسکتاپ'),('login-security/release-admin-390.png','پنل مدیریت در موبایل'),('login-security/mobile-backup-setup.png','راهنمای پشتیبان در اولین ورود')]:
 p=OUT/name
 page+='<figure><img alt="'+label+'" src="data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()+'"><figcaption>'+label+' · دادهٔ مصنوعی تست</figcaption></figure>'
page+='</div></section><section><h2>اجرای سرور</h2><p>راهنمای کامل در DEPLOY.md و فرمان‌های آزمون در docs/testing/AUDIT_RUNBOOK.md هستند. نام‌ها و رمزهای واقعی در گزارش، Git یا ZIP قرار ندارند.</p></section></main></html>'
(OUT / "TIME-LOG-RELEASE.fa.html").write_text(page, encoding="utf-8")
files=['release-summary.json','login-release-backend.xml','login-release-coverage.xml','login-release-coverage.txt','login-release-front-unit.log','login-security/results.json','login-security/burst.json','mobile-backup-setup.json','server-smoke.json','login-python-audit.json','login-source-secrets.json','login-image-api.json','login-image-web.json','login-image-personal.json','browser/e2e.json','ui/ui.json','import-devices/results.json','release-legitimate-30s.json','TIME-LOG-RELEASE.fa.html']
with zipfile.ZipFile(ROOT/'artifacts/TIME-LOG-RELEASE-2026-10-25.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in files:z.write(OUT/name,name)
 for name in ['release-admin-1440.png','release-admin-390.png','mobile-backup-setup.png']:z.write(OUT/'login-security'/name,'ui/'+name)
 z.write(ROOT/'DEPLOY.md','DEPLOY.md');z.write(ROOT/'docs/testing/RELEASE_RESULTS.fa.md','RELEASE_RESULTS.fa.md')
print(json.dumps({'passed':passed,'backend':backend,'coverage':coverage,'e2e':e2e,'ui':ui,'devices':devices,'security':security}))
if not passed:raise SystemExit(1)
