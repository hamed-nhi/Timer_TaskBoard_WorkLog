"use client";
import { useState } from "react";
import useSWR from "swr";
import { errorText, fetcher, post, put } from "@/lib/api";
import { fa } from "@/lib/format";
import { useUi } from "@/shared/ui";

type Policy = { attempts: number; durations_minutes: number[]; unknown_attempts: number; unknown_minutes: number; reset_on_success: boolean; ip_max_failures: number; ip_window_minutes: number; ip_burst: number; ip_hourly: number; global_per_minute: number };
type Ban = { id: number; ip: string; username: string; failures: number; stage: number; banned_until: string | null; active: boolean; reason: string };
type Security = { policy: Policy; bans: Ban[] };

export function LoginSecurity() {
  const { data, error, mutate } = useSWR<Security>("/api/admin/login-protection", fetcher);
  const [draft, setDraft] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast, confirm } = useUi();
  if (error) return <div className="card" role="alert">تنظیمات امنیتی دریافت نشد. <button className="btn btn-outline" onClick={() => mutate()}>تلاش دوباره</button></div>;
  if (!data) return <div className="card" role="status">در حال دریافت تنظیمات امنیت ورود...</div>;
  const policy = draft || data.policy;
  function number(key: Exclude<keyof Policy, "durations_minutes" | "reset_on_success">, label: string, max: number) {
    return <label className="stack">{label}<input type="number" min={1} max={max} required value={policy[key]} onChange={e => setDraft({ ...policy, [key]: Number(e.target.value) })} /></label>;
  }
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true);
    try { await put("/api/admin/login-protection", policy); await mutate(); setDraft(null); toast("سیاست ورود ذخیره شد"); }
    catch (e) { toast(errorText(e)); } finally { setBusy(false); }
  }
  async function release(ban: Ban, reset: boolean) {
    if (!(await confirm(reset ? "مسدودی و تمام سابقهٔ تشدید این ردیف پاک شود؟" : "مسدودی برداشته شود؟ مرحلهٔ تشدید باقی می‌ماند.", "تأیید"))) return;
    setBusy(true);
    try { await post(`/api/admin/login-protection/${ban.id}/unblock`, { reset }); await mutate(); toast("دسترسی آزاد شد"); }
    catch (e) { toast(errorText(e)); } finally { setBusy(false); }
  }
  return <section className="card login-security"><h2>امنیت ورود و مسدودی‌ها</h2>
    <p className="hint">بن رمز برای ترکیب IP و نام کاربری است؛ نام ناشناس می‌تواند کل IP را موقتاً مسدود کند. حساب‌های معتبر، حساب‌هایی هستند که مدیر ساخته است. تغییر تنظیمات، زمان بن‌های موجود را تغییر نمی‌دهد؛ آن‌ها را جدا آزاد کنید.</p>
    <form className="stack" onSubmit={save}>
      <div className="row2">{number("attempts", "تعداد رمز اشتباه در هر مرحله", 20)}{number("unknown_attempts", "تعداد خطای نام کاربری ناشناس", 20)}</div>
      <div className="row2">{policy.durations_minutes.map((value, index) => <label className="stack" key={index}>مدت مرحلهٔ {fa(index + 1)} (دقیقه)<input type="number" min={1} max={525600} required value={value} onChange={e => { const values = [...policy.durations_minutes]; values[index] = Number(e.target.value); setDraft({ ...policy, durations_minutes: values }); }} /></label>)}{number("unknown_minutes", "بن IP برای نام ناشناس (دقیقه)", 525600)}</div>
      <details><summary>محدودیت‌های تکمیلی IP و کل سرویس</summary><div className="row2" style={{ marginTop: 12 }}>
        {number("ip_max_failures", "سقف خطای همهٔ حساب‌ها از یک IP", 1000)}
        {number("ip_window_minutes", "بازهٔ خطای IP (دقیقه)", 1440)}
        {number("ip_burst", "همهٔ درخواست‌های یک IP در دقیقه", 10000)}
        {number("ip_hourly", "همهٔ درخواست‌های یک IP در ساعت", 100000)}
        {number("global_per_minute", "درخواست ورود کل سرویس در دقیقه", 100000)}
      </div><p className="hint">هر محدودیتی زودتر برسد اعمال می‌شود؛ برای آزادترکردن تلاش‌های حساب، سقف IP را هم متناسب تنظیم کنید.</p></details>
      <label className="finish-check"><input type="checkbox" checked={policy.reset_on_success} onChange={e => setDraft({ ...policy, reset_on_success: e.target.checked })} />ورود موفق، سابقهٔ تشدید همان IP و حساب را پاک کند</label>
      <div className="row2"><button className="btn btn-primary" disabled={busy} type="submit">ذخیره سیاست ورود</button><button className="btn btn-outline" type="button" disabled={busy || !draft} onClick={() => setDraft(null)}>لغو تغییرات</button></div>
    </form>
    <h3 style={{ marginTop: 24 }}>مسدودی و سابقهٔ تلاش‌ها</h3><p className="hint">آخرین ۲۰۰ ردیف؛ زمان‌ها به وقت تهران هستند. نشست معتبر موجود با بن ورود بسته نمی‌شود.</p>
    {!data.bans.length ? <p>مسدودی یا سابقه‌ای وجود ندارد.</p> : <div className="table-scroll"><table className="user-table"><thead><tr><th>IP</th><th>حساب</th><th>مرحله / خطا</th><th>وضعیت / پایان</th><th>عملیات</th></tr></thead><tbody>{data.bans.map(b => <tr key={b.id}><td dir="ltr">{b.ip}</td><td>{b.username || "نام ناشناس"}</td><td>{fa(b.stage)} / {fa(b.failures)}</td><td>{b.active ? "مسدود" : "آزاد"}<br /><span dir="ltr">{b.banned_until?.replace("T", " ").slice(0, 19) || "—"}</span></td><td><div className="stack"><button className="btn btn-outline btn-sm" disabled={busy || !b.active} onClick={() => release(b, false)}>رفع بن</button><button className="btn btn-outline btn-sm" disabled={busy} onClick={() => release(b, true)}>پاک‌کردن سابقه</button></div></td></tr>)}</tbody></table></div>}
  </section>;
}
