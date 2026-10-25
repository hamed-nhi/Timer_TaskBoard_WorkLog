"use client";
import { useEffect, useState } from "react";
import { errorText, post } from "@/lib/api";
import { useSettings } from "@/lib/data";
import { refreshAll } from "@/lib/data";
import { useTagActions } from "@/features/tags/components";
import { ThemeSettings } from "@/shared/theme";
import { ImportHistory } from "./import-history";
import { NumInput, useUi } from "@/shared/ui";

export default function SettingsPage() {
  const { data: s } = useSettings();
  const { openManager } = useTagActions();
  const { toast } = useUi();
  const [daily, setDaily] = useState("");
  const [weekly, setWeekly] = useState("");
  const [sheet, setSheet] = useState("");
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (s) { setDaily(String(s.daily_goal_minutes)); setWeekly(String(s.weekly_goal_minutes)); setSheet(s.google_sheet_url || ""); }
  }, [s]);

  async function saveGoals() {
    try {
      await post("/api/settings", { daily_goal_minutes: Number(daily), weekly_goal_minutes: Number(weekly) });
      toast("هدف ساعت کاری ذخیره شد");
      await refreshAll();
    } catch (e) { toast(errorText(e)); }
  }
  async function saveSheet() {
    try { await post("/api/settings", { google_sheet_url: sheet }); toast("لینک ذخیره شد"); } catch (e) { toast(errorText(e)); }
  }
  async function changePassword() {
    setMsg("");
    try {
      await post("/api/me/password", { old: oldPw, new: newPw });
      setOldPw(""); setNewPw("");
      toast("رمز عبور تغییر کرد؛ سایر دستگاه‌ها از حساب خارج شدند");
    } catch (e) { setMsg(errorText(e)); }
  }

  return (
    <div className="settings-grid">
      <ThemeSettings />
      <ImportHistory />
      <div className="card">
        <h2>هدف ساعت کاری</h2>
        <div className="hint" style={{ marginBottom: 10 }}>هدف روزانه و هفتگی که نوار پیشرفت صفحهٔ «امروز» و خط هدف نمودار روزانهٔ داشبورد از آن استفاده می‌کنند.</div>
        <div className="row2">
          <div><label className="lbl">هدف روزانه (دقیقه)</label><NumInput label="هدف روزانه" value={daily} onChange={setDaily} /></div>
          <div><label className="lbl">هدف هفتگی (دقیقه)</label><NumInput label="هدف هفتگی" value={weekly} onChange={setWeekly} /></div>
        </div>
        <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={saveGoals}>ذخیره</button>
      </div>

      <div className="card">
        <h2>تگ‌ها (عنوان استوری‌ها)</h2>
        <div className="hint" style={{ marginBottom: 10 }}>تغییر نام، افزودن، حذف تگ‌های بدون استفاده، ادغام دو تگ و تنظیم بودجه و فیلدهای سامانه‌ی اصلی (همهٔ تسک‌ها منتقل می‌شوند و هیچ زمانی از بین نمی‌رود).</div>
        <button className="btn btn-outline" onClick={openManager}>ویرایش تگ‌ها ✎</button>
      </div>

      <div className="card data-card">
        <h2>داده‌های من</h2>
        <div className="hint" style={{ marginBottom: 10 }}>این خروجی‌ها فقط شامل داده‌های حساب شما هستند. نام فایل با تغییر داده‌های اصلی عوض می‌شود؛ نسخه‌های قبلی پشتیبان خودکار حفظ می‌شوند و دادهٔ بدون تغییر دوباره ذخیره نمی‌شود.</div>
        <div className="shortcuts">
          <a className="btn btn-outline" href="/api/export" style={{ textDecoration: "none", textAlign: "center" }}>دانلود همه‌ی تسک‌ها (اکسل) ⬇</a>
          <a className="btn btn-outline" href="/api/me/backup" style={{ textDecoration: "none", textAlign: "center" }}>دانلود کامل داده (JSON) ⬇</a>
        </div>
        <label className="lbl" style={{ marginTop: 14 }}>لینک Google Sheet برای پشتیبان روزانه <span className="optional">— اختیاری</span></label>
        <input aria-label="لینک شیت شخصی" type="url" dir="ltr" placeholder="https://docs.google.com/spreadsheets/d/..." value={sheet} onChange={(e) => setSheet(e.target.value)} />
        <div className="hint">برای حساب خودتان یک شیت جدا بسازید و آن را با ایمیل سرویس‌اکانت مدیر «ویرایشگر» کنید. پس از فعال‌سازی پشتیبان خودکار، فقط تسک‌های جدید یا تغییرکرده در منبع به‌روزرسانی می‌شوند؛ ردیف‌های بدون تغییر بازنویسی نمی‌شوند. یادداشت‌های شخصی را بیرون از ستون‌های TimeLog بنویسید.</div>
        <button className="btn btn-outline" style={{ marginTop: 8 }} onClick={saveSheet}>ذخیره‌ی لینک</button>
      </div>

      <div className="card">
        <h2>تغییر رمز عبور</h2>
        <div className="stack">
          <input type="password" dir="ltr" autoComplete="current-password" placeholder="رمز فعلی" value={oldPw} onChange={(e) => setOldPw(e.target.value)} />
          <input type="password" dir="ltr" autoComplete="new-password" placeholder="رمز جدید (حداقل ۸ کاراکتر)" value={newPw} onChange={(e) => setNewPw(e.target.value)} />
          <div className="form-error">{msg}</div>
          <button className="btn btn-outline" onClick={changePassword} disabled={!oldPw || newPw.length < 8}>تغییر رمز</button>
        </div>
      </div>
    </div>
  );
}
