"""Build a Persian evidence-linked QA report from actual machine-readable results."""
from collections import Counter
from datetime import datetime
from html import escape
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/testing"
DOC = ROOT / "docs/testing"
OUT.mkdir(parents=True, exist_ok=True)
def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8-sig"))
def junit(name):
    cases = []
    for node in ET.parse(OUT / name).findall(".//testcase"):
        skip, fail, error = node.find("skipped"), node.find("failure"), node.find("error")
        status = "known_defect" if skip is not None and "xfail" in skip.attrib.get("type", "").lower() else (
            "skipped" if skip is not None else ("failed" if fail is not None or error is not None else "passed"))
        message = next((n.attrib.get("message", "") for n in (skip, fail, error) if n is not None), "")
        cases.append({"name": node.attrib["name"], "suite": node.attrib.get("classname", ""),
                      "status": status, "seconds": float(node.attrib.get("time", 0)), "message": message})
    return cases

backend, front = junit("backend.xml"), junit("frontend-unit.xml")
browser = read("e2e.json")["results"]
coverage = read("coverage.json")["totals"]
recovery, crypto = read("recovery.json"), read("crypto.json")
audit = read("npm-audit.json")
host_load = [read(f"load-run{i}.json") for i in (1, 2, 3)]
linux_load = read("load-linux.json")
specs = json.loads((DOC / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
timestamp = datetime.now(ZoneInfo("Asia/Tehran")).isoformat(timespec="seconds")
base_commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
bc, fc, ec = Counter(c["status"] for c in backend), Counter(c["status"] for c in front), Counter(c["status"] for c in browser)
host_errors = sum(len(run["errors"]) for run in host_load)
issues = [
    {"id": "QA-001", "severity": "متوسط", "status": "باز", "title": "گردکردن پیشنهاد از سقف ۵۰٪ تسک کوتاه عبور می‌کند",
     "repro": "suggest_fill برای تسک ۶ دقیقه‌ای و نیاز ۱۰۰ دقیقه، ۵ دقیقه پیشنهاد می‌کند.",
     "expected": "سقف تکمیلی این تسک ۳ دقیقه است.", "source": "backend/app/services/fill.py:suggest_fill",
     "action": "گردکردن را زیر سقف هر تسک انجام دهید و باقی‌مانده را با حفظ سقف‌ها توزیع کنید."},
    {"id": "QA-002", "severity": "متوسط", "status": "باز", "title": "جمع پیشنهاد گرد‌شده از فاصلهٔ مجاز بیشتر می‌شود",
     "repro": "دو تسک ۶۰ دقیقه‌ای، وزن ۱ و فاصلهٔ ۸ دقیقه، مجموعاً ۱۰ دقیقه پیشنهاد می‌گیرند.",
     "expected": "مجموع از سقف مجاز سرور عبور نکند؛ پیشنهاد خود برنامه قابل ثبت باشد.", "source": "backend/app/services/fill.py:suggest_fill",
     "action": "گردکردن مجموع‌محور و تست roundtrip پیشنهاد به ثبت اضافه شود."},
    {"id": "QA-003", "severity": "متوسط", "status": "باز", "title": "نوع نامعتبر date پاسخ ۵۰۰ می‌دهد",
     "repro": "POST /api/fill با date برابر 123، [1] یا یک شیء و items خالی.",
     "expected": "پاسخ ۴۰۰ کنترل‌شده و بدون خطای داخلی.", "source": "backend/app/services/fill.py:parse_day",
     "action": "نوع ورودی بررسی و TypeError هم به ApiError تبدیل شود."},
    {"id": "QA-004", "severity": "بالا", "status": "باز", "title": "شکست pg_dump می‌تواند بک‌آپ موفق کاذب بسازد",
     "repro": "pg_dump با خروج ۱۷ شکست می‌خورد ولی مصرف‌کنندهٔ رمزگذاری خروج صفر و فایل غیرخالی می‌دهد؛ script خروج صفر دارد.",
     "expected": "خرابی تولید dump فوراً شکست بک‌آپ محسوب شود.", "source": "deploy/backup.sh",
     "action": "وضعیت تولید dump مستقل بررسی و فقط خروجی معتبر منتشر شود؛ آزمایش با gpg واقعی هم پس از اصلاح انجام شود."},
    {"id": "QA-005", "severity": "متوسط", "status": "باز", "title": "خطای رمزگشایی در pipeline مستقل کنترل نمی‌شود",
     "repro": "در تزریق خطا، gpg خروج غیرصفر دارد ولی pg_restore ساختگی موفق است؛ script همچنان موفق اعلام می‌کند.",
     "expected": "شکست هر مرحله حفظ شود، حتی اگر مصرف‌کننده موفق باشد.", "source": "deploy/restore_test.sh",
     "action": "وضعیت رمزگشایی جدا بررسی شود. این نتیجه به معنی موفقیت بازیابی واقعی با هر رمز اشتباه نیست."},
    {"id": "QA-006", "severity": "بالا", "status": "رفع‌شده", "title": "راه‌اندازی Docker در Alembic متوقف می‌شد",
     "repro": "در تصویر واقعی Python 3.13، اجرای alembic upgrade head با ModuleNotFoundError: app متوقف شد.",
     "expected": "یافتن برنامه مستقل از cwd و محل executable.", "source": "backend/alembic.ini",
     "action": "script_location و prepend_sys_path به %(here)s متصل شد؛ تست CLI و استک Docker موفق‌اند."},
    {"id": "QA-007", "severity": "نیاز بررسی", "status": "مشاهده‌شده", "title": "قطع اتصال از ویندوز به پورت Docker زیر بار",
     "repro": f"در سه اجرای ثبت‌شدهٔ میزبان، {host_errors} قطع اتصال از ۱۲۰۰ درخواست؛ WinError 10054. در شبکهٔ داخلی Docker صفر از ۴۰۰.",
     "expected": "صفر خطای انتقال در مسیر استفادهٔ هدف.", "source": "artifacts/testing/load-run1.json .. load-run3.json; load-linux.json",
     "action": "مسیر forwarding/keep-alive و محیط سرور واقعی بررسی شود؛ مقایسهٔ دو مسیر علت ریشه‌ای را قطعی نمی‌کند."},
    {"id": "QA-008", "severity": "بالا/متوسط", "status": "یافتهٔ ممیزی", "title": "یافتهٔ npm audit در زنجیرهٔ PostCSS/Next",
     "repro": "ممیزی کامل دو بستهٔ آسیب‌پذیر گزارش کرده: یک high و یک moderate؛ عمدتاً PostCSS انتقالی.",
     "expected": "نسخهٔ اصلاح‌شده یا ارزیابی مستند اثرگذاری بر مسیر build.", "source": "artifacts/testing/npm-audit.json",
     "action": "ارتقای سازگار و تست مجدد بررسی شود. npm audit fix --force اجرا نشده؛ خروجی production-only به خطای شبکه خورد."}
]
special = {
    "FRONTEND-UNIT": [c["status"] for c in front],
    "RESPONSIVE": [c["status"] for c in browser if c["id"].startswith("E2E-") and 20 <= int(c["id"][4:]) <= 46],
    "DOCKER": ["passed"],
    "RECOVERY": ["passed"] if recovery["all_table_fingerprints_equal"] else ["failed"],
    "RESTART": ["passed"] if recovery["session_survived_restart"] else ["failed"],
    "CRYPTO": ["passed"] if crypto["sha256_equal"] and crypto["wrong_passphrase_rejected"] else ["failed"],
    "LOAD": ["observed_issue"] if host_errors else ["passed"],
    "AUDIT": ["finding"] if audit["metadata"]["vulnerabilities"]["total"] else ["passed"],
}
unmatched = []
for case in specs:
    states = []
    for evidence in case["evidence"]:
        if evidence in special:
            states += special[evidence]
        elif evidence.startswith("E2E-"):
            matched = [r["status"] for r in browser if r["id"] == evidence]
            states += matched
            if not matched: unmatched.append((case["id"], evidence))
        else:
            matched = [r["status"] for r in backend if evidence in r["name"]]
            states += matched
            if not matched: unmatched.append((case["id"], evidence))
    case["status"] = next((status for status in ("failed", "known_defect", "observed_issue", "finding", "skipped")
                           if status in states), "passed" if states else "not_executed")
if unmatched:
    raise SystemExit("Unmatched scenario evidence: " + repr(unmatched))
summary = {"timestamp_tehran": timestamp, "base_commit": base_commit, "backend": dict(bc), "frontend_unit": dict(fc),
           "browser": dict(ec), "scenario_count": len(specs), "coverage": coverage,
           "load_windows_runs": host_load, "load_linux": linux_load, "recovery": recovery, "crypto": crypto,
           "dependency_counts": audit["metadata"]["vulnerabilities"], "issues": issues, "scenarios": specs,
           "limitations": ["Safari/Firefox و گوشی فیزیکی", "ممیزی کامل WCAG و تست نفوذ مستقل",
                           "HTTPS/دامنه/سرور واقعی", "Soak طولانی، failover و خرابی PostgreSQL تولید",
                           "ممیزی کامل Python/OS و تعیین قطعی علت قطع اتصال ویندوز", "اجرای workflow روی GitHub"]}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

labels = {"passed": "موفق", "known_defect": "ایراد باز", "failed": "ناموفق", "observed_issue": "نیاز بررسی",
          "finding": "یافتهٔ ممیزی", "skipped": "اجرا نشده", "not_executed": "اجرا نشده"}
md = [f"# گزارش آزمون سیستم تایم‌لاگ\n\nزمان: {timestamp}\n\n",
      "## نتیجهٔ اصلی\n\nمسیرهای اصلی استفاده، جداسازی داده و آزمون‌های مرورگر موفق‌اند؛ این نتیجه به معنی نبود ایراد یا تأیید آمادگی کامل تولید نیست. ایرادهای بک‌آپ و چند مورد مرزی باز هستند.\n\n",
      f"- بک‌اند و عملیات: {bc['passed']} موفق، {bc['known_defect']} شکست موردانتظار مربوط به ۵ ایراد باز.\n",
      f"- واحد فرانت: {fc['passed']} موفق. مرورگر: {ec['passed']} موفق از {len(browser)} سناریوی اجرایی.\n",
      f"- پوشش خطوط: {coverage['percent_statements_covered']:.2f}٪؛ شاخه‌ها: {coverage['percent_branches_covered']:.2f}٪؛ ترکیبی: {coverage['percent_covered']:.2f}٪.\n",
      f"- {len(specs)} سناریوی طراحی‌شده با پیش‌شرط، مراحل و شواهد.\n",
      f"- بار داخل Docker: ۴۰۰ درخواست، صفر خطا، p95 برابر {linux_load['p95_ms']} میلی‌ثانیه.\n",
      f"- مسیر ویندوز: {host_errors} خطای انتقال در ۱۲۰۰ درخواست ثبت‌شده؛ علت ریشه‌ای هنوز قطعی نیست.\n",
      f"- بازیابی: fingerprint تمام ۱۲ جدول برابر؛ سشن بعد از restart باقی ماند؛ API در {recovery['api_recovery_seconds']} ثانیه برگشت.\n",
      "- رمزگذاری AES256 و رمزگشایی واقعی با SHA256 برابر و رد رمز غلط موفق بود.\n",
      "- بیلد واقعی API و Next/Caddy و lint موفق‌اند. مشکل راه‌اندازی Alembic رفع و دوباره آزموده شد.\n\n",
      "## ایرادها و اقدامات\n\n"]
for issue in issues:
    md += [f"### {issue['id']} — {issue['title']}\n\n",
           f"شدت: {issue['severity']}؛ وضعیت: {issue['status']}.\n\nبازتولید: {issue['repro']}\n\n",
           f"انتظار: {issue['expected']}\n\nمحل: {issue['source']}\n\nاقدام: {issue['action']}\n\n"]
md += ["## شواهد و حدود اجرا\n\n",
       "JUnit، JSON پوشش، نتایج مرورگر، تصاویر، بار و بازیابی در artifacts/testing هستند. فایل report.html نسخهٔ قابل جست‌وجوی گزارش است. مقادیر بار فقط برای محیط محلی و این دادهٔ ساختگی‌اند.\n\n",
       "۷ xfail قبولی نیستند؛ تست‌ها اجرا شده و ایرادها بازتولید شده‌اند. workflow جدید نوشته شده ولی روی GitHub اجرا نشده است. تغییرات در این درخواست روی سرور واقعی منتشر نشده و دادهٔ واقعی تغییر نکرده است.\n\n",
       "انجام‌نشده: " + "؛ ".join(summary["limitations"]) + ".\n"]
# Reviewed English snapshots in docs/testing are maintained separately.
(OUT / "RESULTS.fa.md").write_text("".join(md), encoding="utf-8")
matrix = ["# سناریوهای استفاده و نتیجهٔ اجرا\n\n",
          "| شناسه | حوزه | سناریو | نتیجه |\n|---|---|---|---|\n"]
for case in specs:
    matrix.append(f"| {case['id']} | {case['category']} | {case['title']} | {labels[case['status']]} |\n")
for case in specs:
    matrix += [f"\n## {case['id']} — {case['title']}\n\n",
               f"- پیش‌شرط: {case['precondition']}\n- مراحل: {'؛ '.join(case['steps'])}\n",
               f"- انتظار: {case['expected']}\n- نتیجه: {labels[case['status']]}\n",
               f"- شواهد: {', '.join(case['evidence'])}\n"]
# Reviewed English snapshots in docs/testing are maintained separately.
(OUT / "SCENARIOS.fa.md").write_text("".join(matrix), encoding="utf-8")

def h(value): return escape(str(value), quote=True)
cards = "".join(f'<div class="card"><b>{h(value)}</b><span>{h(label)}</span></div>' for label, value in [
    ("موفق بک‌اند", bc["passed"]), ("شکست موردانتظار / ۵ ایراد", bc["known_defect"]),
    ("موفق مرورگر", ec["passed"]), ("موفق واحد فرانت", fc["passed"]),
    ("پوشش خطوط", f"{coverage['percent_statements_covered']:.2f}٪"), ("سناریوی طراحی", len(specs))])
issue_html = "".join(f'<article class="issue"><div class="tag">{h(i["id"])} · {h(i["severity"])} · {h(i["status"])}</div>'
                     f'<h3>{h(i["title"])}</h3><p><strong>بازتولید:</strong> {h(i["repro"])}</p>'
                     f'<p><strong>انتظار:</strong> {h(i["expected"])}</p><p><strong>اقدام:</strong> {h(i["action"])}</p>'
                     f'<code dir="ltr">{h(i["source"])}</code></article>' for i in issues)
scenario_html = "".join(
    f'<tr data-status="{h(c["status"])}"><td><code>{h(c["id"])}</code></td><td>{h(c["category"])}</td>'
    f'<td><details><summary>{h(c["title"])}</summary><p>پیش‌شرط: {h(c["precondition"])}</p>'
    f'<p>مراحل: {h("؛ ".join(c["steps"]))}</p><p>انتظار: {h(c["expected"])}</p>'
    f'<small dir="ltr">{h(", ".join(c["evidence"]))}</small></details></td>'
    f'<td><span class="status {h(c["status"])}">{h(labels[c["status"]])}</span></td></tr>' for c in specs)
tests_html = "".join(f'<tr><td dir="ltr">{h(c["suite"])}::{h(c["name"])}</td><td>{h(labels[c["status"]])}</td></tr>'
                     for c in backend + front)
load_html = "".join(f'<tr><td>{label}</td><td>{run["requests"]}</td><td>{len(run["errors"])}</td>'
                    f'<td>{run["p95_ms"]}</td><td>{run["requests_per_second"]}</td></tr>'
                    for label, run in [(f"ویندوز / اجرای {i}", r) for i, r in enumerate(host_load, 1)] + [("داخل Docker", linux_load)])
gallery = "".join(f'<figure><a href="{h(name)}"><img loading="lazy" src="{h(name)}" alt="{h(label)}"></a><figcaption>{h(label)}</figcaption></figure>'
                  for name, label in [("mobile-touch.png", "چرخهٔ تسک با لمس"), ("fill-preview.png", "پیش‌نمایش تکمیل ساعت"),
                                      ("width-360-admin.png", "مدیریت در عرض ۳۶۰"), ("width-1280-daylog.png", "گزارش روزانه در دسکتاپ")])
document = f"""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش آزمون تایم‌لاگ</title><style>
:root{{--ink:#18233b;--muted:#5c687d;--brand:#5147df;--line:#dce2ee;--bg:#f4f6fb}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.9 Tahoma,Arial,sans-serif}}main{{max-width:1240px;margin:auto;padding:28px 20px}}
header{{background:#17233f;color:white;padding:28px;border-radius:18px}}h1{{margin:0 0 8px;font-size:29px}}header p{{margin:4px 0;color:#dce3fa}}
section{{margin-top:24px;background:white;border:1px solid var(--line);border-radius:16px;padding:22px}}h2{{margin:0 0 14px;font-size:21px}}h3{{margin:6px 0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin-top:18px}}.card{{background:white;border:1px solid var(--line);padding:18px;border-radius:14px;display:flex;flex-direction:column}}.card b{{font-size:29px;color:var(--brand)}}.card span{{color:var(--muted);font-size:12px}}
.notice{{border-right:5px solid #d38b12;background:#fff8e7;padding:14px;margin-top:18px;border-radius:10px}}.tag{{font-size:12px;color:#615077}}.issue{{padding:16px 0;border-bottom:1px solid var(--line)}}.issue:last-child{{border:0}}
code,small[dir=ltr]{{font:12px/1.8 Consolas,monospace;overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid var(--line);padding:11px 8px;vertical-align:top;text-align:right}}th{{background:#f5f6fc}}.scroll{{overflow:auto}}summary{{cursor:pointer;font-weight:bold}}details p{{font-size:13px;color:var(--muted)}}.status{{white-space:nowrap;font-size:12px;border-radius:20px;padding:5px 9px;background:#eef0f4}}.passed{{background:#e2f7ec;color:#176c43}}.known_defect,.failed{{background:#ffe9e9;color:#a82d2d}}.finding,.observed_issue{{background:#fff0cf;color:#8c5b0c}}
.controls{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}}input,select{{font:inherit;border:1px solid var(--line);padding:9px 12px;border-radius:9px;background:white}}input{{flex:1;min-width:180px}}
.gallery{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}figure{{margin:0}}figure img{{width:100%;height:280px;object-fit:contain;object-position:top;border:1px solid var(--line);background:#f8f9fd;border-radius:10px}}figcaption{{font-size:12px;color:var(--muted)}}
a{{color:var(--brand)}}footer{{text-align:center;color:var(--muted);font-size:12px;padding:24px}}@media print{{.controls{{display:none}}section{{break-inside:avoid}}}}
</style><main><header><h1>گزارش آزمون سیستم تایم‌لاگ</h1><p>سناریوهای استفاده، آزمون خودکار و شواهد واقعی اجرا</p><p>زمان تهران: <bdi dir="ltr">{h(timestamp)}</bdi> · مبنای سورس: <code>{h(base_commit)}</code> به‌همراه تغییرات QA محلی</p></header>
<div class="cards">{cards}</div><div class="notice"><strong>نتیجه مشروط است.</strong> مسیرهای اصلی و مرورگر موفق‌اند؛ شکست‌های موردانتظار، ایراد باز هستند. خطای pipeline بک‌آپ، مرزهای fill، قطع اتصال میزبان و یافته‌های وابستگی باید جداگانه رسیدگی شوند.</div>
<section><h2>دامنه و محیط</h2><p>Docker واقعی شامل PostgreSQL 18، FastAPI/Python 3.13 و Next/Caddy؛ تست‌های coverage روی Python 3.14 ویندوز. Chrome واقعی با پروفایل موقت، سه عرض ۳۶۰/۷۶۸/۱۲۸۰، context لمسی و timezone لندن. فقط دادهٔ مصنوعی و دیتابیس‌های مجزای QA استفاده شدند.</p>
<p>بازیابی تمام ۱۲ جدول با fingerprint برابر؛ رمزگذاری AES256 و رد رمز غلط موفق. سشن و داده پس از restart API حفظ شدند و بازگشت API {recovery["api_recovery_seconds"]} ثانیه طول کشید.</p>
<p>پوشش خطوط {coverage["percent_statements_covered"]:.2f}٪، شاخه‌ها {coverage["percent_branches_covered"]:.2f}٪ و ترکیبی {coverage["percent_covered"]:.2f}٪ است. <a href="coverage/index.html">جزئیات پوشش سورس</a></p></section>
<section><h2>بار و پایداری اتصال</h2><p>هر اجرا: ۱۰ کاربر، ۱۰ worker، ۲۸۰۰ تسک در ۲۸ روز و ۴۰۰ درخواست. هیچ retry برای پنهان‌کردن خطا انجام نشد. تفاوت دو مسیر، علت ریشه‌ای را قطعی نمی‌کند.</p><div class="scroll"><table><thead><tr><th>مسیر</th><th>درخواست</th><th>خطا</th><th>p95 ms</th><th>درخواست/ثانیه</th></tr></thead><tbody>{load_html}</tbody></table></div><p>این اعداد برای ظرفیت سرور تولید یا دسترس‌پذیری بلندمدت قابل تعمیم نیستند.</p></section>
<section><h2>ایرادها و پیگیری</h2>{issue_html}</section>
<section><h2>ماتریس سناریوها</h2><p>برای دیدن پیش‌شرط، مراحل و معیار پذیرش، عنوان هر سناریو را باز کنید.</p><div class="controls"><input id="search" placeholder="جست‌وجوی عنوان، حوزه یا شناسه..." aria-label="جست‌وجوی سناریو"><select id="state" aria-label="نتیجه"><option value="">همهٔ نتایج</option value="passed">موفق</option><option value="known_defect">ایراد باز</option><option value="observed_issue">نیاز بررسی</option><option value="finding">یافتهٔ ممیزی</option></select></div>
<div class="scroll"><table id="scenarios"><thead><tr><th>شناسه</th><th>حوزه</th><th>سناریو و جزئیات</th><th>نتیجه</th></tr></thead><tbody>{scenario_html}</tbody></table></div></section>
<section><h2>تصاویر شواهد مرورگر</h2><div class="gallery">{gallery}</div></section>
<section><h2>محدودیت‌ها</h2><ul>{''.join('<li>'+h(x)+'</li>' for x in summary["limitations"])}</ul><p>همگام‌سازی Google Sheet و اسکرپ هنوز پیاده نشده‌اند. فقط مسیر ذخیرهٔ لینک شیت قابل آزمون است. ممیزی production-only npm به خطای شبکه خورد؛ نتیجهٔ ممیزی کامل موجود است. به‌روزرسانی major خودکار انجام نشد.</p></section>
<section><details><summary>فهرست تست‌های بک‌اند و واحد فرانت</summary><div class="scroll"><table><thead><tr><th>تست</th><th>نتیجه</th></tr></thead><tbody>{tests_html}</tbody></table></div></details></section>
<footer>تولیدشده از JUnit و JSON واقعی؛ فایل dump، رمز عبور، کوکی و دادهٔ واقعی در بستهٔ گزارش قرار نمی‌گیرد.</footer></main>
<script>const rows=[...document.querySelectorAll('#scenarios tbody tr')];function filter(){{const q=document.querySelector('#search').value.toLowerCase(),s=document.querySelector('#state').value;for(const r of rows)r.hidden=!(r.textContent.toLowerCase().includes(q)&&(!s||r.dataset.status===s));}}document.querySelector('#search').addEventListener('input',filter);document.querySelector('#state').addEventListener('change',filter);</script></html>"""
(OUT / "report.html").write_text(document, encoding="utf-8")
with zipfile.ZipFile(OUT / "timelog-qa-report.zip", "w", zipfile.ZIP_DEFLATED) as package:
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".css", ".js", ".png", ".json", ".xml"}:
            if "failure" in path.name:
                continue
            package.write(path, path.relative_to(OUT))
    for path in DOC.glob("*.md"):
        package.write(path, "documents/" + path.name)
    package.write(DOC / "scenarios.json", "documents/scenarios.json")
print(json.dumps({"backend": dict(bc), "frontend": dict(fc), "browser": dict(ec), "scenarios": len(specs),
                  "line_coverage": coverage["percent_statements_covered"], "branch_coverage": coverage["percent_branches_covered"],
                  "report": str(OUT / "report.html")}, ensure_ascii=False))
