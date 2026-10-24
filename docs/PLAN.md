# TimeLog Web — پلن اجرایی

> به‌روزرسانی ۲۰۲۶-۱۰-۲۴ — درخواست جدید کاربر جای تصمیم «کاتالوگ مشترک» در متن زیر را گرفته است: نوع گزارش، پروژه و استوری برای هر حساب خصوصی است. همهٔ کاربران در صفحهٔ مدیریت به کاتالوگ خود دسترسی دارند؛ فقط مدیریت حساب‌ها مختص ادمین است. API جدید `/api/catalog`، مایگریشن `0002_private_catalog.py` و CLI با `import-catalog FILE --user USERNAME` اجرا می‌شوند. کاتالوگ مرتبط با داده‌های قدیمی برای هر مالک کپی و اتصال‌ها منتقل می‌شود؛ اصل رکوردهای مشترک بدون مالک و خارج از API حفظ می‌شود. این مایگریشن در جریان توسعه فقط روی دیتابیس تست اجرا شده است؛ پیش از اعمال روی دادهٔ واقعی بک‌آپ الزامی است.


این سند برای مدلی نوشته شده که کد را می‌زند. هر فاز را جدا انجام بده، تست بزن، commit کن، بعد برو فاز بعد.
منبع منطق کسب‌وکار: نسخه‌ی دسکتاپ در `C:\Users\hnahali\Documents\Folder\Hamed-stuff\time-sys` (`app.py`, `static/app.js`, `calendar_events.py`, `tests/`).

---

## ۰. قواعد غیرقابل‌مذاکره

1. **به نسخه‌ی دسکتاپ دست نزن.** مخزن `time-sys` فقط خوانده می‌شود. هیچ فایلی در آن تغییر نکند و هیچ commitی در آن زده نشود.
2. **`tasklog.db` واقعی را هرگز برای نوشتن باز نکن.**
   - اسکریپت انتقال اول یک کپی می‌گیرد: `sqlite3 backup` به `C:\TimeLogBackups\before_web_migration_<ts>.db`.
   - بعد فقط از روی همان کپی، و با `mode=ro`، می‌خواند.
3. **جدا بودن داده‌ی کاربرها:**
   - هر query روی داده‌ی کاربر باید `user_id` را فیلتر کند.
   - id یک تسک یا تگِ کاربر دیگر باید **404** برگرداند، نه 403.
4. **هیچ secretی در git نرود:** نه `.env`، نه رمز، نه کلید سرویس گوگل، نه dump.
5. **over-engineering ممنوع:**
   - نه Redis، نه Celery، نه Kubernetes، نه microservice، نه GraphQL.
   - JWT هم نه؛ session در دیتابیس کافی است.
   - Repository pattern روی SQLAlchemy هم نه.
6. **سؤال اول:** اگر رفتار یک endpoint در دسکتاپ مبهم بود، اول کد دسکتاپ و تستش را بخوان. اگر باز مبهم بود، از کاربر بپرس.
7. **زبان:** کاربر فارسی‌زبان است. پیام‌های UI و خطاها فارسی، و کامنت‌های کد انگلیسی و کم باشد.

---

## ۱. تصمیم‌های گرفته‌شده

| موضوع | تصمیم |
|---|---|
| مخزن | جدید و **private** با نام `timelog-web`، در پوشه‌ی `C:\Users\hnahali\Documents\Folder\Hamed-stuff\timelog-web`. remote را کاربر خودش می‌سازد و push می‌کند. |
| بک‌اند | Python 3.12، FastAPI، SQLAlchemy 2 (sync)، psycopg 3، Alembic، pydantic-settings، argon2-cffi، jdatetime، openpyxl |
| دیتابیس | PostgreSQL 18 |
| فرانت | Next.js 15 (App Router) + React 19 + TypeScript + Tailwind CSS 4. خروجی استاتیک با `output: 'export'`، پس در production هیچ Node serverی اجرا نمی‌شود. |
| دریافت داده در فرانت | `lib/api.ts` (یک wrapper روی fetch) + `swr` |
| فونت | Vazirmatn از `@fontsource/vazirmatn`، self-hosted، بدون Google Fonts |
| تاریخ شمسی | تبدیل‌ها در بک‌اند انجام می‌شود (مثل دسکتاپ). فرانت فقط `Intl.DateTimeFormat('fa-IR-u-ca-persian')` و ارقام فارسی دارد و کتابخانه‌ی تاریخ ندارد. |
| ورود | نام کاربری و رمز، session در cookie، و قفل بعد از ۳ تلاش ناموفق در ۲۰ دقیقه |
| ثبت‌نام | آزاد نیست. ادمین حساب می‌سازد. |
| کاتالوگ استوری | مشترک بین همه‌ی کاربران و قابل ویرایش فقط توسط ادمین. بعداً از سامانه‌ی اصلی اسکرپ می‌شود؛ فعلاً فقط import از JSON. |
| حضور | فقط دستی. ورود خودکار، ping و تشخیص خاموش شدن کامپیوتر **حذف** می‌شوند. یک یادآوری اضافه می‌شود: «تسک در حال اجراست ولی ورود به شرکت ثبت نشده». |
| آفلاین | ندارد |
| موبایل | باید کاملاً ریسپانسیو باشد (بخش ۷). یک PWA manifest هم دارد تا بشود «افزودن به صفحه‌ی اصلی» زد، ولی service worker و کش آفلاین ندارد. |
| سرور | VPS لینوکسی داخل ایران، با Docker Compose و Caddy (HTTPS خودکار) |
| منطقه‌ی زمانی | `Asia/Tehran`. همه‌ی timestampها در دیتابیس `timestamptz` هستند و «امروز» با همین منطقه‌ی زمانی حساب می‌شود. |
| بک‌آپ | pg_dump شبانه روی سرور. کامپیوتر کاربر هر روز آن را می‌کشد و در `D:\My Drive\TimeLogBackups\web` می‌گذارد، که هم روی کامپیوتر می‌ماند و هم با Google Drive همگام می‌شود. Google Sheet هر کاربر اختیاری است (فاز ۷). |

> **نکته‌ی ایران:** Docker Hub، npm و Google ممکن است از IP ایران بسته باشند.
> - Docker: `registry-mirrors` در `/etc/docker/daemon.json`، مثلاً `https://docker.arvancloud.ir`.
> - npm و pip: آدرس registry از build arg خوانده شود (`NPM_REGISTRY` و `PIP_INDEX_URL`).
> - Google Sheet: هیچ‌جا فرض نکن Google در دسترس است.

---

## ۲. ساختار مخزن

```
timelog-web/
├─ README.md                 # راه‌اندازی محلی + استقرار (فارسی)
├─ .gitignore                # .env, *.db, backups/, node_modules, .next, out, __pycache__
├─ .env.example
├─ docker-compose.yml        # db, api, web (caddy)
├─ docker-compose.dev.yml    # فقط Postgres برای توسعه‌ی محلی
├─ .github/workflows/ci.yml
├─ backend/
│  ├─ pyproject.toml         # یا requirements.txt + requirements-dev.txt
│  ├─ Dockerfile
│  ├─ alembic.ini
│  ├─ alembic/versions/
│  ├─ app/
│  │  ├─ main.py             # FastAPI app, routers, exception handlers
│  │  ├─ config.py           # Settings (pydantic-settings)
│  │  ├─ db.py               # engine, SessionLocal, get_db dependency
│  │  ├─ models.py           # all SQLAlchemy models (یک فایل)
│  │  ├─ schemas.py          # Pydantic request/response models
│  │  ├─ auth.py             # hashing, sessions, current_user, require_admin, rate limit
│  │  ├─ jalali.py           # g2j, j2g, month names, weekday names (از app.py)
│  │  ├─ calendar_events.py  # کپی عینی از دسکتاپ
│  │  ├─ timecalc.py         # effective_minutes, segments, overlap, duration (از app.py)
│  │  ├─ fill.py             # presence_sanity, suggest_fill, constants (از app.py)
│  │  ├─ routers/
│  │  │  ├─ auth.py  tasks.py  planned.py  tags.py  presence.py
│  │  │  ├─ reports.py       # timesheet, dashboard, tag-summary, entry-report, export, daylog
│  │  │  ├─ fill.py  calendar.py  settings.py  catalog.py  admin.py  me.py
│  │  ├─ cli.py              # create-user, reset-password, import-desktop, import-catalog
│  │  └─ jobs/sheets_sync.py # فاز ۷
│  └─ tests/
│     ├─ conftest.py         # Postgres test DB, client, login helper, two users
│     └─ test_*.py
├─ frontend/
│  ├─ package.json  next.config.ts  tsconfig.json  postcss.config.mjs
│  ├─ public/ manifest.webmanifest, icons/
│  ├─ app/
│  │  ├─ layout.tsx          # <html lang="fa" dir="rtl">, font, shell
│  │  ├─ login/page.tsx
│  │  ├─ (app)/layout.tsx    # auth guard + nav (top on desktop, bottom on mobile)
│  │  ├─ (app)/page.tsx      # امروز
│  │  ├─ (app)/planned/page.tsx  dashboard/  calendar/  timesheet/  tasks/  daylog/  settings/  admin/
│  ├─ components/            # TaskTimer, TaskCard, PresenceCard, FillDialog, StoryPicker, Modal/Sheet, ...
│  └─ lib/ api.ts, fa.ts (faDigits, fmtDuration), types.ts
└─ deploy/
   ├─ Caddyfile
   ├─ backup.sh              # pg_dump + gpg + retention
   ├─ restore_test.sh
   └─ pull_backup.ps1        # روی کامپیوتر کاربر
```

---

## ۳. مدل داده (Postgres)

همه‌ی جدول‌ها `id bigint identity PK` دارند. `created_at` از نوع `timestamptz default now()` است. «کاربرِ» بی‌قید یعنی FK به `users`.

```text
users(id, username citext unique, password_hash, display_name, is_admin bool, is_active bool, created_at)
sessions(id, user_id, token_hash text unique, created_at, expires_at, last_seen_at, user_agent)
login_attempts(id, username, ip inet, success bool, at timestamptz)   -- index (username, at), (ip, at)

-- کاتالوگ مشترک (ادمین)
report_types(id, name unique, sort)
projects(id, name unique, sort)
stories(id, project_id FK, name, sort, unique(project_id, name))

-- داده‌ی هر کاربر
tags(id, user_id, name, budget_minutes real null, budget_since date null,
     report_type_id FK null, story_id FK null, fill_weight real null, created_at,
     unique(user_id, lower(name)))
tasks(id, user_id, jalali_year, jalali_month, jalali_day, gregorian_date date,
      title, start_time time null, end_time time null, duration_minutes real null,
      status text check in ('running','paused','done'), accumulated_minutes real default 0,
      segment_started_at timestamptz null, tag_id FK null, entered_main_system bool,
      meeting_with text null, meeting_minutes real null, adjust_minutes real default 0,
      report_type_id FK null, outside_company bool, planned_flag bool, fill_minutes real default 0,
      created_at)
      -- index (user_id, gregorian_date), (user_id, status)
task_segments(id, task_id FK on delete cascade, started_at timestamptz, ended_at timestamptz null)
planned_tasks(id, user_id, jalali_year, jalali_month, jalali_day, title, tag_id FK null, created_at)
presence_segments(id, user_id, started_at timestamptz, ended_at timestamptz null, note text, kind text)
user_settings(user_id, key, value text, PK(user_id, key))
   -- daily_goal_minutes, weekly_goal_minutes, fill_target_percent, google_sheet_url
audit_log(id, user_id, kind text, payload jsonb, at)
   -- kind: 'task_deleted' | 'fill_rollback' | 'tag_merge'
   -- جایگزین deleted_tasks, fill_rollback_log, tag_merge_log
```

**مقادیر status:** این‌ها را از دسکتاپ کپی کن (`grep "status" app.py`). اگر مقداری غیر از سه مقدار بالا دیدی، به همان شکل نگهش دار.

**نگاشت‌های دسکتاپ:**
- `tags.report_type` و `tags.project` / `tags.story` (متن) → `report_type_id` و `story_id`، از طریق جست‌وجوی اسم در کاتالوگ.
- `tasks.report_type` (متن) → `report_type_id`.

**دیگر:**
- Alembic فقط یک migration اولیه دارد. هر تغییر بعدی migration جدید و **additive** است.
- `company_type`، `company_project` و `company_story` در پاسخ تسک همان قاعده‌ی دسکتاپ را دارند: override خود تسک ← `meeting_with` ← نوع گزارشِ تگ. پروژه و استوری از استوریِ تگ می‌آیند.

---

## ۴. احراز هویت و امنیت

- **هش رمز:** argon2id (از `argon2-cffi`). حداقل طول رمز ۸ کاراکتر است.
- **ورود (`POST /api/auth/login {username, password}`):**
  1. اگر در ۲۰ دقیقه‌ی اخیر ۳ تلاش ناموفق یا بیشتر برای این username ثبت شده بود، **429** برگردان، با پیام «۳ بار رمز اشتباه وارد شد. X دقیقه‌ی دیگر دوباره امتحان کنید.» و هدر `Retry-After`.
  2. همین قفل را برای IP هم بگذار، با سقف ۱۰ تلاش در ۲۰ دقیقه، برای جلوگیری از امتحان کردن نام‌های کاربری مختلف.
  3. اگر رمز اشتباه بود یا کاربر وجود نداشت یا غیرفعال بود، 401 با یک پیام یکسان برگردان: «نام کاربری یا رمز اشتباه است».
  4. همه‌ی تلاش‌ها را در `login_attempts` ثبت کن.
  5. اگر ورود موفق بود، یک token تصادفی بساز (`secrets.token_urlsafe(32)`). در DB فقط `sha256` آن ذخیره شود.
  6. cookie `tl_session` را بگذار: `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=30 روز`.
- **خروج:** `POST /api/auth/logout` session را از DB پاک می‌کند.
- **`current_user` (dependency):** cookie را می‌خواند، session معتبر و منقضی‌نشده را پیدا می‌کند، و `last_seen_at` را حداکثر یک بار در ساعت به‌روز می‌کند. اگر چیزی پیدا نشد 401.
- **`require_admin`:** اگر کاربر ادمین نبود 403.
- **CSRF:** هر درخواست POST، PUT یا DELETE باید هدر `X-Requested-With: timelog` داشته باشد، وگرنه 403. ترکیب این با SameSite=Lax و هم‌دامنه بودن فرانت و API از CSRF جلوگیری می‌کند.
- **CORS:** فعال نکن. فرانت و API روی یک دامنه‌اند (`/` و `/api`).
- **تغییر رمز خود کاربر:** `POST /api/me/password {old, new}`. بعد از تغییر، بقیه‌ی sessionهای آن کاربر حذف شوند.
- **ادمین:**
  - `GET/POST /api/admin/users`
  - `PUT /api/admin/users/{id}` برای فعال/غیرفعال کردن و تغییر نام نمایشی
  - `POST /api/admin/users/{id}/reset-password` که یک رمز موقت برمی‌گرداند
  - CRUD کاتالوگ زیر `/api/admin/catalog/...`
- **CLI:**
  ```bash
  python -m app.cli create-user <username> --admin
  ```
  رمز با `getpass` پرسیده شود و در آرگومان نیاید.
- **لاگ:** رمز و token هرگز در لاگ نیایند.

---

## ۵. API

همه‌ی مسیرها با `/api` شروع می‌شوند و همه به‌جز login نیاز به ورود دارند.
**شکل request و response همان دسکتاپ باشد**، تا منطق `static/app.js` راحت منتقل شود. برای هر endpoint، تابع متناظر در `app.py` منبع رفتار است.

| endpoint وب | تابع دسکتاپ | توضیح |
|---|---|---|
| `GET /api/me` | — | `{id, username, display_name, is_admin}` |
| `GET /api/today`, `/api/month-days`, `/api/shift-date`, `/api/yesterday-titles` | `api_today`, `api_month_days`, `api_shift_date`, `yesterday_titles` | |
| `GET/POST /api/tags`, `PUT/DELETE /api/tags/{id}`, `PUT /api/tags/{id}/budget`, `POST /api/tags/{id}/merge`, `PUT /api/tags/{id}/company` | همان‌ها | company: `{report_type_id, story_id, fill_weight}` |
| `GET /api/company-catalog` | `company_catalog` | از جدول‌های کاتالوگ مشترک خوانده شود |
| `GET/POST /api/presence`, `GET /api/presence/history`, `POST /api/presence/start\|pause\|finish`, `PUT/DELETE /api/presence/{id}` | همان‌ها | **حذف شوند:** `/ping`, `/auto`, `/auto-setting`, `presence_last_seen`, `presence_close_dead_session`. پاسخ state یک فیلد جدید `needs_checkin` دارد: true وقتی امروز تسک running هست ولی segment حضورِ باز وجود ندارد. |
| `GET/POST /api/settings` | `api_get_settings`, `api_update_settings` | بر اساس user_settings |
| `GET /api/goal-progress` | `goal_progress` | |
| `GET/POST /api/planned`, `PUT/DELETE /api/planned/{id}`, `POST /api/planned/{id}/start` | همان‌ها | start باید `planned_flag` را بگذارد |
| `GET/POST /api/tasks`, `GET /api/tasks/paused`, `POST /api/tasks/{id}/pause\|resume\|stop\|reopen`, `GET /api/tasks/{id}/segments`, `POST /api/tasks/{id}/entered`, `POST /api/tasks/{id}/company`, `PUT/DELETE /api/tasks/{id}` | همان‌ها | delete ← `audit_log('task_deleted', payload کامل + segments)` |
| `GET /api/fill-suggestion`, `POST /api/fill`, `POST /api/fill/rollback` | همان‌ها | rollback ← audit_log |
| `GET /api/timesheet`, `/api/dashboard`, `/api/tag-summary`, `/api/calendar`, `/api/entry-report` | همان‌ها | |
| `GET /api/export` | `export_excel` | فقط داده‌ی خود کاربر، با همان ستون‌ها |
| `GET /api/me/backup` | — | JSON کامل داده‌های خود کاربر (دانلود) |
| `/api/backup`, `/api/drive-backup` | — | **حذف**؛ بک‌آپ کار سرور است |

**قواعدی که باید دقیقاً منتقل شوند** (هرکدام با تست منتقل‌شده از `tests/` دسکتاپ):
- محاسبه‌ی مدت:
  - `effective_minutes`، `duration_from_segments`، `compute_duration`، `parse_adjust` و `adjust_minutes`.
  - مکث و ادامه: segmentها و `accumulated_minutes`.
  - `reopen`.
  - ویرایش ساعت شروع و پایان (`update_task`).
- **عدم هم‌پوشانی:** `assert_no_overlap` روی تسک‌های **همان کاربر** اعمال شود. هم‌پوشانی با کاربر دیگر مهم نیست.
- **فقط یک تسک running برای هر کاربر:** شروع تسک جدید، تسک قبلی را pause می‌کند. رفتار دقیقش را در `create_task` چک کن.
- **تکمیل ساعت:**
  - `presence_sanity` در همه‌ی حالت‌ها: جمعه، بدون حضور، حضور کمتر از تسک‌ها، بیش از ۱۱ ساعت، کم کردن ۳۰ دقیقه ناهار، و هشدار «پایان کار» زده نشده.
  - `suggest_fill` با سقف ۵۰٪ و گرد کردن ۵ دقیقه‌ای، `FILL_MAX_PERCENT=95`، و چک سقف در سرور داخل `apply_fill`.
  - هشدار «خروج از روی خاموش شدن کامپیوتر حدس زده شده» دیگر معنی ندارد. متنش را به «پایان کار زده نشده» تغییر بده.
- **بودجه‌ی تگ:** `budget_info` و `tag_spent_minutes`.
- **ادغام تگ:** `merge_tags`.
- **مقایسه‌ی داشبورد:** `build_comparison` و `aligned_minutes`.
- **تقویم:** `calendar_events.py` بدون تغییر کپی شود.
- **اعتبارسنجی ورودی:** `clean_title` (۵۰۰ کاراکتر)، `clean_tag_name` (۶۰ کاراکتر)، `TIME_RE`، `clean_jalali`، و نرمال‌سازی ی و ک عربی (`tag_key`). این‌ها در Pydantic یا همان توابع پیاده شوند.

**خطاها:** شکل `{"error": "پیام فارسی"}` و کدهای 400، 401، 403، 404، 409 و 429، مثل `handle_api_error` در دسکتاپ.

---

## ۶. فرانت‌اند

**پوسته:**
- `layout.tsx` با `lang="fa" dir="rtl"`. رنگ‌ها CSS variable هستند، با حالت تاریک از طریق `prefers-color-scheme`.
- گارد ورود: اگر `/api/me` جواب 401 داد، به `/login` برو.
- `lib/api.ts`:
  - هدر `X-Requested-With: timelog` را می‌گذارد و `credentials: 'same-origin'` است.
  - روی 401 به login redirect می‌کند.
  - روی خطا، `error` را از پاسخ برمی‌دارد و throw می‌کند.

**صفحه‌ها:** معادل تب‌های دسکتاپ هستند. ترتیب و محتوا را از `templates/index.html` و `static/app.js` بگیر.

| مسیر | محتوا |
|---|---|
| `/login` | فرم نام کاربری و رمز، نمایش پیام قفل (429) |
| `/` امروز | کارت حضور (شروع، مکث، پایان، باکس گزارش با تکمیلی و دکمه‌ی تکمیل ساعت)، بنر یادآوری `needs_checkin`، فرم شروع تسک با انتخاب استوری، تسک در حال اجرا با تایمر زنده، تسک‌های مکث‌شده، لیست تسک‌های امروز، پیشرفت هدف |
| `/planned` | برنامه‌ریزی روزها، شروع از برنامه |
| `/dashboard` | داشبورد و مقایسه، خلاصه‌ی تگ‌ها و بودجه |
| `/calendar` | تقویم ماهانه‌ی شمسی با مناسبت‌ها |
| `/timesheet` | تایم‌شیت هفتگی |
| `/tasks` | همه‌ی تسک‌ها و ویرایش |
| `/daylog` | گزارش روزانه با ستون‌ها و جمع پایین صفحه و rollback، دکمه‌ی کپی همه (همان ترتیب ستون‌های دسکتاپ)، و تیک «وارد سامانه شد» |
| `/settings` | هدف‌ها، درصد تکمیل، تغییر رمز، لینک Google Sheet، دانلود اکسل و JSON، مدیریت تگ‌ها (استوری‌ها) |
| `/admin` | فقط ادمین: کاربران و کاتالوگ |

**دیالوگ تکمیل ساعت:** همان سه مرحله‌ی دسکتاپ.
1. جمله‌ی پیشنهاد با هشدارها
2. ویرایش دستی
3. پیش‌نمایش، سپس تأیید نهایی

پیشنهاد همیشه تازه از سرور گرفته می‌شود. اگر جمع بیش از سقف بود، خطا نشان داده شود و دکمه‌ی «بعدی» غیرفعال شود.

**انتخاب استوری:** گروه‌بندی بر اساس پروژه (مثل `optgroup` در `populateTagSelect`). گزینه‌های «(بدون استوری)» و «+ افزودن استوری جدید» هم باشند.

**تایمر:** هر ثانیه از روی `segment_started_at` و `accumulated_minutes` در کلاینت محاسبه می‌شود. با هر focus روی تب، داده دوباره از سرور گرفته شود (`swr`، `revalidateOnFocus`).

---

## ۷. ریسپانسیو و موبایل (الزامی)

**اندازه‌ها:** باید در عرض **360px** (گوشی کوچک)، 768px و 1280px درست کار کند. در هیچ عرضی scroll افقی صفحه نباشد.

**ناوبری:**
- زیر 768px: **نوار تب پایین** با ۵ آیکن و برچسب: امروز، برنامه، گزارش روزانه، داشبورد، بیشتر. «بیشتر» یک sheet باز می‌کند با بقیه‌ی صفحه‌ها.
- بالای 768px: نوار بالا.
- نوار پایین `padding-bottom: env(safe-area-inset-bottom)` داشته باشد.

**تسک در حال اجرا:**
- در موبایل یک **نوار چسبان** بالای نوار تب نشان داده شود: عنوان، تایمر و دکمه‌های مکث و پایان.
- از هر صفحه‌ای قابل دیدن باشد.

**جدول‌ها** (گزارش روزانه، همه‌ی تسک‌ها، تایم‌شیت):
- زیر 640px هر ردیف به یک **کارت** تبدیل می‌شود: عنوان، ساعت‌ها، ثبت‌شده و تکمیلی، و نوع/پروژه/استوری در یک خط کوچک.
- چک‌باکس‌ها و دکمه‌ی ویرایش در پایین کارت قرار می‌گیرند.
- جمع‌ها زیر لیست می‌آیند.
- تایم‌شیت هفتگی در موبایل یا scroll افقی **داخل خود جدول** دارد، یا لیست روزها به‌صورت accordion است.

**دیالوگ‌ها:** در موبایل bottom sheet تمام‌عرض باشند، با ارتفاع حداکثر 90vh، scroll داخلی و دکمه‌های اصلی چسبیده به پایین.

**لمس و فرم‌ها:**
- همه‌ی هدف‌های لمسی حداقل **44×44px** باشند.
- اندازه‌ی فونت inputها حداقل 16px باشد، تا iOS هنگام فوکوس صفحه را zoom نکند.
- برای ساعت `<input type="time">` و برای عدد `inputMode="numeric"`.

**تقویم:** شبکه‌ی ۷ ستونه با سلول‌های کوچک. جزئیات روز در یک sheet زیر تقویم باز می‌شود.

**PWA:**
- `manifest.webmanifest` با `name: "تایم‌لاگ"`، `dir: "rtl"`، `lang: "fa"`، `display: "standalone"`، `theme_color` و آیکن‌های 192 و 512 (آیکن را از دسکتاپ بگیر: `tools/generate_icon.py` یا آیکن موجود).
- `apple-touch-icon` هم باشد.

**معیار پذیرش موبایل:**
- در Chrome DevTools با عرض 360×740 همه‌ی صفحه‌ها بدون scroll افقی باز شوند.
- شروع، مکث و پایان تسک، ورود به شرکت، و کل جریان تکمیل ساعت با لمس قابل انجام باشد.
- اسکرین‌شات این عرض‌ها برای کاربر گرفته شود.

---

## ۸. استقرار

**`docker-compose.yml`:**
- **`db`:** `postgres:18` با volume `pgdata`، healthcheck، و **بدون** پورت باز به بیرون.
- **`api`:** از `backend/Dockerfile` ساخته می‌شود (python:3.12-slim، uvicorn با 2 worker).
  - هنگام شروع `alembic upgrade head` اجرا شود.
  - env از `.env` خوانده شود.
  - فقط داخل شبکه‌ی compose در دسترس باشد.
- **`web`:** `caddy:2` + Dockerfile چندمرحله‌ای.
  - مرحله‌ی اول: `node:22` و `npm ci && npm run build` با `NPM_REGISTRY` به‌عنوان build arg.
  - مرحله‌ی دوم: Caddy، که خروجی `out/` را سرو می‌کند.
  - پورت‌های 80 و 443 باز.

**`deploy/Caddyfile`:**
```
{$DOMAIN} {
  encode gzip
  handle /api/* { reverse_proxy api:8000 }
  handle { root * /srv/www; try_files {path} {path}.html {path}/index.html /index.html; file_server }
  header { Strict-Transport-Security "max-age=31536000"; X-Content-Type-Options nosniff; Referrer-Policy same-origin }
}
```
اگر دامنه نداشتیم، `DOMAIN=:443` با `tls internal`.

**`.env.example`:** `DOMAIN`، `POSTGRES_PASSWORD`، `DATABASE_URL`، `APP_TZ=Asia/Tehran`، `BACKUP_PASSPHRASE_FILE`، `GOOGLE_SA_JSON` (اختیاری).

**استقرار دستی روی سرور:**
```bash
git pull && docker compose up -d --build
```

**CI (`.github/workflows/ci.yml`):**
- job بک‌اند: سرویس `postgres:18`، `pip install`، `pytest`.
- job فرانت: `npm ci`، `npm run lint`، `npm run build`.
- deploy خودکار ندارد.

---

## ۹. بک‌آپ

**`deploy/backup.sh`:** با cron میزبان، هر شب ساعت ۲:۳۰ اجرا شود.
1. `docker compose exec -T db pg_dump -Fc -U timelog timelog` را با `gpg --symmetric --batch --passphrase-file` رمزگذاری کن و در `/srv/timelog/backups/daily/timelog_<date>.dump.gpg` بنویس.
2. اگر امروز جمعه بود، یک کپی هم در `weekly/` بگذار.
3. **نگهداری:** ۱۴ نسخه‌ی روزانه و ۸ نسخه‌ی هفتگی.
4. اگر اندازه‌ی فایل صفر بود یا `pg_dump` خطا داد، exit غیرصفر بده و در لاگ بنویس.
5. symlink `latest.dump.gpg` را به‌روز کن.

**`deploy/restore_test.sh`:**
- آخرین dump را در یک دیتابیس موقت `timelog_restore_test` بازیابی کند.
- تعداد ردیف‌های `tasks` و `users` را چاپ کند، و بعد آن دیتابیس را drop کند.
- ماهی یک بار با cron اجرا شود.

**`deploy/pull_backup.ps1`:** روی کامپیوتر کاربر.
- با `scp` (OpenSSH ویندوز) و کلید SSH، `latest.dump.gpg` را به `D:\My Drive\TimeLogBackups\web\timelog_<date>.dump.gpg` بکشد.
- ۳۰ نسخه‌ی آخر را نگه دارد.
- در README، دستور ثبت در Task Scheduler (روزانه + هنگام logon) نوشته شود.
- کلید SSH را کاربر خودش می‌سازد. اسکریپت هیچ رمزی در خودش ندارد.

**دانلود داده‌ی هر کاربر:** در صفحه‌ی تنظیمات، دکمه‌های دانلود اکسل و JSON داده‌ی خود کاربر.

---

## ۱۰. انتقال داده‌ی دسکتاپ

```bash
python -m app.cli import-desktop <path-to-copy.db> --user <username>
```

1. فقط روی **کپی** کار کند. اگر مسیر داده‌شده همان `tasklog.db` اصلی بود، اجرا را رد کند.
2. فایل را با `sqlite3.connect('file:...?mode=ro', uri=True)` باز کند.
3. اگر کاربر مقصد از قبل تسک داشت، متوقف شود. انتقال فقط یک بار و روی حساب خالی انجام می‌شود.
4. **کاتالوگ:** اول کاتالوگ از `settings.company_catalog` دسکتاپ وارد جدول‌های مشترک شود. این کار idempotent است و چیزی که از قبل هست تکرار نمی‌شود.
5. **انتقال:** همه‌چیز در **یک transaction** منتقل شود:
   - tags → `story_id` و `report_type_id` با جست‌وجوی اسم.
   - planned_tasks.
   - tasks: idها نگاشت می‌شوند، و تاریخ و ساعت‌های متنی محلی با منطقه‌ی زمانی Tehran به `timestamptz` تبدیل می‌شوند.
   - task_segments.
   - presence_segments.
   - settings → user_settings. کلیدهای `presence_last_seen` و `default_tags_seeded` رد شوند.
   - deleted_tasks، tag_merge_log و fill_rollback_log → audit_log.
6. **چک نهایی:** قبل از commit، تعداد تسک‌ها و `SUM(duration_minutes)`، `SUM(fill_minutes)`، `SUM(adjust_minutes)`، تعداد segmentها و تعداد presence را با مبدأ مقایسه کن. اگر حتی یکی فرق داشت، rollback کن و خطا بده. الان مبدأ ۷۷ تسک و ۹۵۶۱.۱ دقیقه دارد.
7. **تست:** یک SQLite نمونه‌ی کوچک در `tests/fixtures` بساز و import روی آن را تست کن. داده‌ی واقعی را در تست استفاده نکن.

---

## ۱۱. تست‌ها

**زیرساخت:**
- pytest + `fastapi.testclient`.
- دیتابیس تست Postgres واقعی است، از `TEST_DATABASE_URL`. در توسعه‌ی محلی `docker-compose.dev.yml` آن را بالا می‌آورد.
- بین تست‌ها جدول‌ها truncate شوند.
- `conftest.py` دو کاربر `alice` و `bob` و یک helper ورود دارد.

**تست‌های منتقل‌شده:** تست‌های دسکتاپ برای منطق (زمان، هم‌پوشانی، مکث، planned، تکمیل ساعت، بودجه، اکسل، تایم‌شیت) به API جدید منتقل شوند. تست‌های مخصوص pywebview، drive و ping منتقل **نشوند**.

**تست‌های جدید الزامی:**
- **جدا بودن داده:** bob هیچ تسک، تگ، planned، حضور، تنظیمات یا خروجی‌ای از alice نمی‌بیند و نمی‌تواند تغییرش دهد. برای هر نوع، هم list و هم get/put/delete با id آلیس → 404.
- **قفل ورود:** ۳ رمز اشتباه → تلاش چهارم حتی با رمز درست 429 می‌گیرد. بعد از ۲۰ دقیقه (زمان در تست mock شود) ورود دوباره ممکن است.
- **session:** logout و session منقضی‌شده → 401. تغییر رمز بقیه‌ی sessionها را باطل می‌کند.
- **CSRF:** POST بدون هدر → 403.
- **ادمین:** کاربر عادی روی `/api/admin/*` → 403.
- **`needs_checkin`:** درست محاسبه شود.
- **import:** چک‌های بخش ۱۰، و رد شدن import روی حساب غیرخالی.
- **فرانت:** فقط `npm run build` و lint. تست E2E لازم نیست.

---

## ۱۲. فازها و معیار پذیرش

بعد از هر فاز یک commit زده شود. همه‌ی تست‌ها باید سبز باشند و یک گزارش کوتاه فارسی برای کاربر نوشته شود.

| فاز | کار | معیار پذیرش |
|---|---|---|
| **1. اسکلت** | ساخت مخزن، این PLAN به `docs/PLAN.md`، `.gitignore`، compose dev، FastAPI با `/api/health`، Alembic، مدل‌ها و migration اولیه، Next.js خالی با RTL و فونت، CI | `pytest` و `npm run build` سبز، `alembic upgrade head` روی Postgres 18 بدون خطا |
| **2. ورود** | users، sessions، login_attempts، login/logout/me، CSRF، CLI create-user، صفحه‌ی login | تست‌های امنیتی بخش ۱۱ سبز |
| **3. هسته‌ی تسک** | jalali، timecalc، tags، tasks (همه‌ی actionها)، planned، settings، goal-progress، catalog (خواندن) + تست‌های منتقل‌شده + تست جدا بودن داده | رفتار برابر با دسکتاپ، تست‌ها سبز |
| **4. حضور و تکمیل ساعت** | presence دستی و `needs_checkin`، fill-suggestion/fill/rollback، audit_log | تست‌های fill دسکتاپ منتقل و سبز |
| **5. گزارش‌ها** | timesheet، dashboard، tag-summary، calendar، entry-report، export اکسل، `/api/me/backup` | خروجی اکسل همان ستون‌های دسکتاپ را دارد |
| **6. فرانت** | همه‌ی صفحه‌های بخش ۶ با ریسپانسیو بخش ۷، admin، PWA manifest | معیار موبایل بخش ۷، اسکرین‌شات‌ها در 360 و 1280 |
| **7. import و استقرار و بک‌آپ** | `import-desktop`، Dockerfileها، Caddyfile، backup/restore/pull scripts، README استقرار. Google Sheet sync فقط اگر کاربر تأیید کرد که سرور به Google دسترسی دارد. | اجرای کامل `docker compose up` به‌صورت محلی، import روی یک کپی از DB واقعی با چک‌های برابر، و بازیابی موفق یک dump |

**Google Sheet (اختیاری، بعد از فاز ۷):**
- `app/jobs/sheets_sync.py` با یک service account.
- کاربر لینک شیت خودش را در تنظیمات می‌گذارد و شیت را با ایمیل service account به اشتراک می‌گذارد.
- هر شب تب `Tasks` بازنویسی می‌شود، با همان ستون‌های اکسل.
- اگر برای کاربری خطا داد، فقط لاگ شود و بقیه‌ی کاربران ادامه پیدا کنند.
- اجرا با cron میزبان: `docker compose exec api python -m app.jobs.sheets_sync`.

---

## ۱۳. سؤال‌های باز (جواب کاربر تا الان نیامده)

1. دامنه دارید؟ این روی `DOMAIN` در Caddy اثر دارد. فازهای ۱ تا ۶ بدون جواب هم جلو می‌روند.
2. خروجی این دستور روی سرور چیست؟
   ```bash
   curl -sS -o /dev/null -w "%{http_code}\n" https://sheets.googleapis.com
   ```
   جوابش تعیین می‌کند Google Sheet شدنی است یا نه.
3. سیستم‌عامل و RAM سرور چیست و Docker نصب است؟
4. حدوداً چند کاربر خواهید داشت؟
