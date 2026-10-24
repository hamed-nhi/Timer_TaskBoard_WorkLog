# HANDOFF — تایم‌لاگ وب (برای مدل بعدی)

> خلاصه‌ی کامل کار انجام‌شده، دستورها، قوانین و محدودیت‌ها. قبل از هر کاری این فایل و `docs/PLAN.md` را بخوان.

## 1. پروژه چیست
- **تایم‌لاگ**: ثبت ساعت کار روزانه، رابط فارسی RTL، تقویم جلالی.
- **نسخه دسکتاپ** (Flask + SQLite + pywebview) در `C:\Users\hnahali\Documents\Folder\Hamed-stuff\time-sys` است و **دست‌نخورده می‌ماند**.
- **نسخه وب چندکاربره** (همین ریپو، `E:\workload`): FastAPI + PostgreSQL 18 + Next.js (خروجی استاتیک). همه‌ی قابلیت‌های دسکتاپ پورت شده‌اند.
- کاربر: حامد. با او **فارسی و کوتاه** حرف بزن.

## 2. تصمیم‌های کاربر (نباید دوباره پرسیده شوند)
- بک‌اند FastAPI، ساختار استاندارد، نه over-engineered. فرانت مدرن استاندارد. Postgres 18.
- **موبایل‌ریسپانسیو اجباری**.
- هر کاربر نام‌کاربری/رمز خودش را دارد و **فقط داده‌ی خودش** را می‌بیند. ادمین حساب می‌سازد.
- ورود: حداکثر **۳ تلاش ناموفق در ۲۰ دقیقه**.
- داده‌ی دسکتاپ خود کاربر باید منتقل شود و فقط خودش ببیند.
- هر کاربر می‌تواند لینک Google Sheet بدهد برای بک‌آپ روزانه‌ی داده‌اش.
- سرور: لینوکس داخل ایران.
- کاتالوگ شرکت (نوع گزارش، پروژه، استوری) **مشترک** است. استوری‌ها بعداً از «سامانه‌ی اصلی» اسکرپ می‌شوند.
- حضور فقط **دستی** + یادآور «تسک شروع شده ولی ورود ثبت نشده». حالت آفلاین: **نه**.
- GitHub: private، فقط دوستان. **کاربر خودش push می‌کند؛ تو push نکن.**
- بک‌آپ: Google Drive و کامپیوتر خودش.

## 3. قوانین ثابت (سخت)
1. **هرگز داده‌ی واقعی را حذف/گم/تغییر نده.** زمان اصلی تسک را قابلیت «پر کردن» هرگز نباید تغییر دهد.
2. فقط روی **کپی دیتابیس** یا پورت دیگر تست کن. `tasklog.db` واقعی فقط **خوانده** می‌شود (روی کپی یا read-only).
3. مایگریشن‌ها **فقط افزایشی**.
4. قبل از هر تغییر روی داده‌ی واقعی بک‌آپ بگیر: `C:\TimeLogBackups\before_<what>_<ts>.db`.
5. هیچ secret / `.env` / dump در git نرود. (`.gitignore` پوشش می‌دهد.)
6. بعد از هر فیچر commit کن. پیام commit با این خط تمام شود: `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (یا مدل خودت).
7. پاسخ به کاربر: فارسی، کوتاه. **حالت ponytail**: کوچک‌ترین تغییر کامل؛ آخر هر پاسخ یک‌دو خط «چه چیزی انجام/بررسی نشد و ریسک».
8. قبل از کار خارجی/برگشت‌ناپذیر (push، حذف، ارسال) تأیید بگیر.
9. sync ریپوی **دسکتاپ** (نه وب) به Drive: `robocopy . "D:\My Drive\TimeLogSource" /E /XD venv .venv __pycache__ .git .pytest_cache /XF *.db *.log drive_backup_status.json drive_backup_log.txt /NFL /NDL /NJH /NJS /NP` (خروجی 0 یا 1 = موفق). برای `E:\workload` چنین دستوری داده نشده.

## 4. معماری و قراردادها
- **بک‌اند** `backend/app`: `main.py` (هندلرها، CSRF middleware، health)، `config.py` (Settings: `database_url`, `app_tz`, `cookie_secure`, ...)، `db.py` (wrapper `Db` روی Session: `?`→`%s`، `insert` با `RETURNING id`، `lock_user` با `pg_advisory_xact_lock`)، `models.py`، `timeutil.py`، `timecalc.py`، `auth.py`، `deps.py`، `routers/*` (auth, admin, tags, tasks, planned, presence, fill, reports, settings_me)، `cli.py`، `importer.py`، `catalog.py`.
- **زمان**: همه‌ی زمان‌ها naive وقت تهران (`timestamp`، نه timestamptz). `tasks.gregorian_date` نوع `date`؛ `start_time/end_time` رشته‌ی `HH:MM`. `now_local()` با `Asia/Tehran`.
- **جداسازی**: هر کوئری per-user روی `user_id` فیلتر می‌شود. id دیگران → 404 (حذف تسک دیگران بی‌صدا هیچ‌کاری نمی‌کند).
- **احراز هویت**: کوکی `tl_session` (در DB فقط sha256 توکن)؛ CSRF با هدر `X-Requested-With: timelog` روی غیر-GET (وگرنه 403)؛ قفل ورود: ۳ شکست/نام‌کاربری/۲۰ دقیقه، ۱۰ شکست/IP، فقط شکست‌های بعد از آخرین موفقیت، 429 با `Retry-After`؛ پیام 401 یکسان برای کاربر/رمز اشتباه؛ تغییر رمز بقیه‌ی نشست‌ها را می‌بندد.
- **کاتالوگ مشترک**: `report_types`, `projects`, `stories` فقط ادمین ویرایش می‌کند؛ آیتم استفاده‌شده حذف نمی‌شود (409). تگ‌ها = عنوان استوری. نوع شرکتی تسک: override تسک ← `meeting_with` ← نوع تگ.
- **قواعد پر کردن/حضور** (پورت از دسکتاپ): `FILL_MAX_PERCENT=95`، `FILL_CAP_RATIO=0.5`، `FILL_STEP=5`، `FILL_MAX_PRESENCE=660`، `FILL_NO_LUNCH_AFTER=360`، `FILL_ASSUMED_LUNCH=30`، `FILL_DAY_OFF=4`. سرور سقف ۹۵٪ را روی `POST /api/fill` اجرا می‌کند. لاگ بازگشت در `audit_log` با نوع `fill_rollback`. انواع audit: `task_deleted`, `fill_rollback`, `tag_merge`.
- **حضور**: فقط دستی؛ `needs_checkin` وقتی تسک در حال اجراست و بخش حضور باز نیست. endpointهای ping/auto حذف شده‌اند.
- **فرانت** `frontend`: Next.js 15 App Router، خروجی استاتیک (`output:"export"`, `trailingSlash`) در production؛ در dev، rewrite از `/api` به `http://127.0.0.1:8000`. React 19، TypeScript، SWR، CSS دستی در `app/globals.css`، فونت Vazirmatn، فقط تم روشن. اعداد فارسی با `fa()`. `/api/today` مقدار `server_time` می‌دهد (`SKEW` در `lib/data.tsx`) تا ساعت مرورگر با منطقه‌ی دیگر درست بتپد.
- **موبایل** (≤760px): نوار پایین (امروز، برنامه‌ریزی، گزارش روزانه، داشبورد، بیشتر)، باکس «بیشتر»، نوار تسک در حال اجرا، دیالوگ‌های bottom-sheet، هدف لمسی ۴۴px، جدول گزارش روزانه به کارت تبدیل می‌شود. PWA manifest بدون service worker.

## 5. دستورها
Dev (Windows). Postgres dev روی پورت 5442:
```
cd E:\workload; docker compose -f docker-compose.dev.yml up -d
```
بک‌اند (PowerShell):
```
cd E:\workload\backend; $env:DATABASE_URL="postgresql+psycopg://timelog:timelog@localhost:5442/timelog"; $env:COOKIE_SECURE="false"; ..\venv\Scripts\python -m uvicorn app.main:app --port 8000
```
فرانت (PowerShell؛ از `npm.cmd` استفاده کن چون `npm.ps1` مسدود است):
```
cd E:\workload\frontend; npm.cmd run dev
```
تست‌ها (روی DB جدا `timelog_test` در همان Postgres؛ باید وجود داشته باشد): `cd backend; ..\venv\Scripts\python -m pytest -q` ← ۱۵۷ تست پاس.
بیلد فرانت: `npm.cmd run build` (۱۱ مسیر استاتیک)، لینت: `npm.cmd run lint`.
CLI: `python -m app.cli create-user <name> [--admin] [--display-name X]` | `reset-password <name>` | `import-catalog <file>` | `import-desktop <db> --user <name> [--dry-run]`.
کاربر dev محلی: `hamed` / `dev-password-1` (فقط DB dev).
استقرار: `.env` از `.env.example` بساز؛ `docker compose up -d --build`. بک‌آپ: `deploy/backup.sh` (cron شبانه، ۱۴ روزانه + ۸ هفتگی، gpg)، `deploy/restore_test.sh`، `deploy/pull_backup.ps1` (روی ویندوز کاربر). CI: `.github/workflows/ci.yml` (postgres:18 با `POSTGRES_DB=timelog_test`، pytest، npm ci/lint/build).

## 6. گوتچاهای ابزار/محیط
- shell کاربر گاهی CMD است، گاهی PowerShell؛ `&&` در PowerShell 5 کار نمی‌کند و `cd /d` فقط CMD است. دستور را مخصوص همان shell بده.
- در ابزار Bash، heredoc حاوی آپوستروف خراب می‌شود؛ از ابزار Write یا اسکریپت Python استفاده کن.
- `tests/__init__.py` نباید وجود داشته باشد (import از conftest می‌شکند).
- ستون `login_attempts.ip` نوع inet است؛ `client_ip()` اعتبارسنجی می‌کند؛ TestClient با `client=("127.0.0.1", 50000)` ساخته می‌شود.
- جدول `login_attempts` بعد از هر تست truncate می‌شود (وگرنه ردیف تاریخ‌آینده نشت می‌کند).
- Docker روی دستگاه کاربر دسترسی ضعیف به pypi دارد؛ build ایمیج `api` timeout خورد.

## 7. وضعیت و کارهای باقی‌مانده
**انجام و تست‌شده**: بک‌اند کامل (۱۵۷ تست)، importer دسکتاپ (dry-run روی کپی: ۸۲ تسک، ۹۸۱۴.۴ دقیقه، ۱۶۱ سگمنت، ۹ حضور، ۱۵ تگ — همه برابر)، فرانت (همه‌ی صفحه‌ها، بدون اسکرول افقی در عرض ۳۶۰)، لاگین محلی کاربر موفق بود.

**انجام‌نشده / تست‌نشده**:
1. تست کامل دستی کاربر (چرخه‌ی تسک، حضور، fill، ایزولیشن دو کاربر، قفل ورود، موبایل) — در جریان.
2. `docker compose up` کامل هرگز اجرا نشده (فقط `config -q` اوکی). روی سرور واقعی باید تست شود.
3. همگام‌سازی روزانه با **Google Sheet** پیاده نشده (لینک ذخیره و اعتبارسنجی می‌شود ولی چیزی ارسال نمی‌شود). منتظر پاسخ کاربر: آیا سرور به `https://sheets.googleapis.com` دسترسی دارد؟ اگر بله: `app/jobs/sheets_sync.py` با cron.
4. اسکرپ استوری‌ها از سامانه‌ی اصلی.
5. فعلاً فقط ادمین کاتالوگ را ویرایش می‌کند (دوستان نمی‌توانند استوری اضافه کنند).
6. تست خودکار فرانت وجود ندارد (فقط build + lint).
7. ریسک‌ها: زمان naive تهران؛ دسترسی Docker/npm/Google از سرور ایران تأییدنشده؛ دامنه، سیستم‌عامل/رم سرور و تعداد کاربران هنوز نامشخص.
8. اجرای واقعی importer برای حساب کاربر روی سرور (روی کپی `tasklog.db`، با `--dry-run` اول، بک‌آپ قبلش).
9. کاربر باید ریپوی private را خودش بسازد و push کند.
