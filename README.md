# تایم‌لاگ (نسخه وب)

ثبت ساعت کار روزانه برای چند کاربر. هر کاربر نام‌کاربری و رمز خودش را دارد و فقط داده‌ی خودش را می‌بیند.
بک‌اند FastAPI + PostgreSQL 18، فرانت Next.js (خروجی استاتیک)، تقویم جلالی، رابط فارسی و موبایل‌پسند.
نسخه دسکتاپ (Flask/pywebview) جداست و دست‌نخورده می‌ماند. جزئیات طراحی در `docs/PLAN.md`.

## اجرای محلی (توسعه)

```bash
docker compose -f docker-compose.dev.yml up -d          # فقط Postgres روی پورت 5442
cd backend
python -m venv ../venv && ../venv/Scripts/pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://timelog:timelog@localhost:5442/timelog COOKIE_SECURE=false
alembic upgrade head
python -m app.cli create-user hamed --admin             # رمز را می‌پرسد
uvicorn app.main:app --port 8000
# ترمینال دوم
cd frontend && npm ci && npm run dev                    # http://localhost:3000
```

تست‌ها (روی دیتابیس جدا `timelog_test`، باید یک‌بار ساخته شود):

```bash
cd backend && pytest -q
```

## استقرار روی سرور لینوکس

1. Docker و Docker Compose نصب باشد. در ایران اگر دسترسی نیست در `.env` مقدار `DOCKER_REGISTRY=docker.arvancloud.ir/` و میرور `NPM_REGISTRY` و `PIP_INDEX_URL` را بگذارید.
2. `cp .env.example .env` و `DB_PASSWORD`، `BACKUP_PASSPHRASE` و `SITE_ADDRESS` (دامنه برای https خودکار) را پر کنید. فایل `.env` هرگز commit نمی‌شود.
3. `docker compose up -d --build` (مایگریشن‌ها خودکار اجرا می‌شوند؛ فقط افزایشی هستند).
4. ساخت ادمین: `docker compose exec api python -m app.cli create-user <نام> --admin`
5. ادمین از صفحه «مدیریت» کاربران را می‌سازد و کاتالوگ شرکت (نوع گزارش، پروژه، استوری) را مشترک نگه می‌دارد.

## انتقال داده‌ی دسکتاپ (فقط برای صاحب داده)

همیشه روی **کپی** دیتابیس کار کنید، نه فایل اصلی:

```bash
copy tasklog.db desktop_copy.db
docker compose exec api python -m app.cli import-desktop /tmp/desktop_copy.db --user hamed --dry-run
# اگر شمارش‌ها (تسک، دقیقه، سگمنت، حضور) درست بود، بدون --dry-run
```

داده فقط به حساب همان کاربر وصل می‌شود.

## بک‌آپ

- `deploy/backup.sh` هر شب (cron: `0 3 * * * /opt/timelog/deploy/backup.sh`): `pg_dump` رمزگذاری‌شده، ۱۴ نسخه روزانه و ۸ هفتگی.
- `deploy/restore_test.sh`: آخرین بک‌آپ را در دیتابیس موقت بازیابی می‌کند و تعداد تسک‌ها را نشان می‌دهد. ماهی یک‌بار اجرا کنید؛ بک‌آپ بازیابی‌نشده بک‌آپ نیست.
- `deploy/pull_backup.ps1` روی ویندوز خودتان (Task Scheduler): بک‌آپ‌ها را به `D:\My Drive\TimeLogBackups\web` می‌آورد، که با Google Drive همگام می‌شود.
- هر کاربر در تنظیمات می‌تواند خروجی کامل داده‌ی خودش را دانلود کند.

## وضعیت

- همه‌ی قابلیت‌های دسکتاپ پورت شده‌اند، با جداسازی کامل داده‌ی کاربران.
- ورود: حداکثر ۳ تلاش ناموفق در ۲۰ دقیقه برای هر نام‌کاربری.
- هنوز نیست: همگام‌سازی روزانه با Google Sheet (لینک در تنظیمات ذخیره می‌شود ولی ارسالی انجام نمی‌شود؛ منوط به دسترسی سرور به Google)، اسکرپ استوری‌ها از سامانه‌ی اصلی، حالت آفلاین (عمداً).
