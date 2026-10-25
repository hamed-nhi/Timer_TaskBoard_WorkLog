"use client";
import { ReactNode, useState } from "react";
import { errorText, post } from "@/lib/api";
import { useSettings } from "@/lib/data";

export function BackupSetupGate({ children }: { children: ReactNode }) {
  const { data, error, mutate } = useSettings();
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  if (error) return <section className="card" role="alert">تنظیمات پشتیبان دریافت نشد. <button className="btn btn-outline" onClick={() => mutate()}>تلاش دوباره</button></section>;
  if (!data) return <div role="status">در حال بررسی تنظیمات پشتیبان...</div>;
  if (data.backup_setup_done) return <>{children}</>;
  async function finish(withSheet: boolean) {
    setBusy(true); setMessage("");
    try { await post("/api/settings", { backup_setup_done: true, ...(withSheet ? { google_sheet_url: url || data?.google_sheet_url || "" } : {}) }); await mutate(); }
    catch (e) { setMessage(errorText(e)); } finally { setBusy(false); }
  }
  return <section className="card backup-setup" aria-labelledby="backup-setup-title">
    <h2 id="backup-setup-title">اولین قدم: از داده‌هایتان نسخهٔ پشتیبان داشته باشید</h2>
    <p>برای اینکه یک نسخهٔ دیگر از زمان‌های ثبت‌شده داشته باشید، شیت شخصی خودتان را معرفی کنید. دانلود Excel هم همیشه از تنظیمات در دسترس شماست.</p>
    <ol><li>با حساب Google خود، یک <a href="https://sheets.google.com/create" target="_blank" rel="noreferrer">شیت خالی و خصوصی بسازید</a>. ثبت‌نام جداگانه‌ای در TIME LOG لازم نیست.</li>
      <li>در بخش Share شیت، ایمیل زیر را با نقش <b>Editor / ویرایشگر</b> اضافه کنید. شیت را Public نکنید و دسترسی Anyone with the link لازم نیست.</li></ol>
    {data.backup_service_email ? <p className="presence-note" dir="ltr" style={{ overflowWrap: "anywhere", userSelect: "all" }}>{data.backup_service_email}</p> : <p className="presence-note">مدیر هنوز ایمیل سرویس‌اکانت را تنظیم نکرده است. می‌توانید بعداً از تنظیمات لینک را ثبت کنید؛ در این وضعیت ارسال به Google Sheets فعال اعلام نمی‌شود.</p>}
    <p className="hint">فقط یک شیت مخصوص همین حساب معرفی کنید. زمان‌بندی سرور باید فعال باشد تا روزانه ساعت ۳ بامداد تهران نسخهٔ شخصی JSON/Excel ساخته شود و در صورت تنظیم سرویس‌اکانت و دسترسی شیت، تغییرات به Google Sheets ارسال شوند. تغییر دستی شیت، دادهٔ اصلی برنامه را عوض نمی‌کند.</p>
    <form className="stack" onSubmit={e => { e.preventDefault(); void finish(true); }}>
      <label className="stack">لینک Google Sheet شخصی<input type="url" dir="ltr" placeholder="https://docs.google.com/spreadsheets/d/..." value={url || data.google_sheet_url} onChange={e => setUrl(e.target.value)} /></label>
      <div className="form-error" role="alert">{message}</div>
      <button className="btn btn-primary" disabled={busy || !(url || data.google_sheet_url)} type="submit">ذخیره لینک و ادامه</button>
      <button className="btn btn-outline" disabled={busy} type="button" onClick={() => finish(false)}>فعلاً بدون شیت ادامه می‌دهم</button>
      <a className="btn btn-outline" href="/api/export">دانلود داده‌های من به Excel</a>
    </form>
    <p className="hint">ثبت لینک، تأیید ارسال موفق نیست. پشتیبان کامل رمزگذاری‌شدهٔ دیتابیس هم مسئولیت مدیر سرور است؛ فایل تسک Excel جای آن را نمی‌گیرد.</p>
  </section>;
}
