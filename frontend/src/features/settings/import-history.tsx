"use client";
import { useState } from "react";
import { api, errorText } from "@/lib/api";
import { refreshAll } from "@/lib/data";
import { fa, fmtDuration } from "@/lib/format";

type Issue = { sheet: string; row: number; message: string };
type Preview = {
  columns: string[]; mapping: Record<string, string>; fields: {key:string; label:string}[]; revision:string;
  new_rows:number; duplicate_rows:number; new_minutes:number; total_rows:number; error_count:number; warning_count:number;
  errors:Issue[]; warnings:Issue[];
  preview:{date:string; title:string; start:string|null; end:string|null; duration:number; tag:string; duplicate:boolean; sheet:string; row:number}[];
};
type Imported = {imported:number; duplicates:number; minutes:number};

export function ImportHistory() {
  const [file,setFile]=useState<File|null>(null);
  const [mapping,setMapping]=useState<Record<string,string>>({});
  const [year,setYear]=useState("");
  const [preview,setPreview]=useState<Preview|null>(null);
  const [dirty,setDirty]=useState(true);
  const [mappingOpen,setMappingOpen]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [result,setResult]=useState<Imported|null>(null);
  async function run(commit=false) {
    if(!file||busy)return;
    setBusy(true);setError("");setResult(null);
    try {
      const form=new FormData();form.append("file",file);form.append("mapping",JSON.stringify(mapping));form.append("year",year);
      if(commit) {
        form.append("revision",preview?.revision||"");
        const data=await api<Imported>("/api/me/import/commit","POST",form);
        setResult(data);setPreview(null);setDirty(true);await refreshAll();
      } else {
        const data=await api<Preview>("/api/me/import/preview","POST",form);
        setPreview(data);setMapping(data.mapping);setDirty(false);setMappingOpen(!data.mapping.date||!data.mapping.title);
      }
    } catch(e) {setError(errorText(e));}
    finally {setBusy(false);}
  }
  return <section className="card import-card" aria-labelledby="import-title" aria-busy={busy}>
    <h2 id="import-title">انتقال سابقه از Excel یا CSV</h2>
    <p className="hint">تسک‌های تمام‌شدهٔ نسخهٔ دسکتاپ یا ابزار قبلی را به حساب خودتان بیاورید. ابتدا پیش‌نمایش می‌بینید؛ ردیف‌های تکراری رد می‌شوند و داده‌های موجود بازنویسی نمی‌شوند.</p>
    <div className="shortcuts import-samples">
      <a className="btn btn-outline" href="/api/me/import/template/xlsx">نمونهٔ اکسل ↓</a>
      <a className="btn btn-outline" href="/api/me/import/template/csv">نمونهٔ CSV ↓</a>
      <a className="btn btn-outline" href="/api/me/import/template/txt">راهنمای تبدیل برای مدل ↓</a>
    </div>
    <details className="how-to"><summary>فایل باید چه شکلی باشد؟</summary>
      <p>تاریخ کامل مثل <bdi dir="ltr">1405/08/03</bdi> شمسی یا <bdi dir="ltr">2026-10-25</bdi> میلادی، شرح فعالیت و مدت به دقیقه لازم است. به‌جای مدت می‌توانید شروع و پایان به شکل <bdi dir="ltr">09:30</bdi> بدهید. ارقام فارسی هم پذیرفته می‌شوند.</p>
      <p>خروجی اکسل تایم‌لاگ مستقیم خوانده می‌شود؛ برای فایل‌های دیگر ستون‌ها را در پیش‌نمایش انتخاب کنید. اگر تاریخ فقط ماه و روز دارد، سال باید در نام برگه باشد یا اینجا وارد شود. ردیف نمونه را با داده‌های خودتان جایگزین کنید.</p>
      <p>مدت واقعی و تکمیلی جدا حفظ می‌شوند. حضور، جزئیات وقفه‌ها و برنامه‌های آینده از این قالب منتقل نمی‌شوند. فرمول‌ها را پیش از بارگذاری به مقدار ثابت تبدیل کنید.</p>
    </details>
    <div className="stack">
      <label className="lbl" htmlFor="import-file">فایل سابقه (XLSX یا CSV، حداکثر ۵ مگابایت و ۵۰۰۰ سطر)</label>
      <input id="import-file" type="file" accept=".xlsx,.csv" disabled={busy} onChange={e=>{
        const selected=e.target.files?.[0]||null;setPreview(null);setMapping({});setResult(null);setError("");setDirty(true);
        if(selected&&selected.size>5*1024*1024){setFile(null);setError("فایل باید حداکثر ۵ مگابایت باشد");}else setFile(selected);
      }}/>
      <label className="lbl" htmlFor="import-year">سال شمسی فایل، فقط برای تاریخ‌های بدون سال — اختیاری</label>
      <input id="import-year" type="text" inputMode="numeric" maxLength={4} placeholder="مثلاً ۱۴۰۵" value={year} disabled={busy} onChange={e=>{setYear(e.target.value);setDirty(true);}}/>
      <button className="btn btn-outline" disabled={!file||busy} onClick={()=>run()}>پیش‌نمایش فایل</button>
    </div>
    {error&&<p className="form-error" role="alert">{error}</p>}
    {busy&&<p className="hint" role="status">در حال بررسی و پردازش فایل…</p>}
    {result&&<p className="presence-note" role="status">{fa(result.imported)} تسک با {fmtDuration(result.minutes)} وارد شد؛ {fa(result.duplicates)} ردیف تکراری وارد نشد.</p>}
    {preview&&<div className="import-review">
      <h3>بررسی فایل</h3>
      <details className="how-to" open={mappingOpen} onToggle={e=>setMappingOpen(e.currentTarget.open)}><summary>انتخاب یا اصلاح ستون‌ها</summary><p className="hint">تاریخ، شرح فعالیت و مدت یا ساعت‌ها لازم‌اند؛ بقیهٔ ستون‌ها اختیاری‌اند. اگر ستونی درست تشخیص داده نشده، آن را انتخاب و دوباره پیش‌نمایش بگیرید.</p>
      <div className="import-mapping">{preview.fields.map(field=><label className="lbl" key={field.key}>{field.label}
        <select aria-label={`ستون ${field.label}`} value={mapping[field.key]||""} disabled={busy} onChange={e=>{setMapping({...mapping,[field.key]:e.target.value});setDirty(true);}}>
          <option value="">انتخاب نشده</option>{preview.columns.filter(Boolean).map(name=><option key={name} value={name}>{name}</option>)}
        </select>
      </label>)}</div></details>
      {dirty?<p className="hint" role="status">ستون‌ها یا سال تغییر کرده‌اند؛ پیش‌نمایش را دوباره بگیرید.</p>:<>
        <p>{fa(preview.new_rows)} تسک جدید، {fa(preview.duplicate_rows)} تکراری؛ زمان واقعی جدید: {fmtDuration(preview.new_minutes)}</p>
        {!!preview.error_count&&<div role="alert"><p className="form-error">{fa(preview.error_count)} خطا؛ تا رفع خطاها هیچ ردیفی وارد نمی‌شود.</p><ul className="import-issues">{preview.errors.map((issue,i)=><li key={i}>{issue.sheet}، سطر {fa(issue.row)}: {issue.message}</li>)}</ul></div>}
        {!!preview.warning_count&&<details><summary>{fa(preview.warning_count)} نکته دربارهٔ داده‌ها</summary><ul className="import-issues">{preview.warnings.map((issue,i)=><li key={i}>{issue.sheet}، سطر {fa(issue.row)}: {issue.message}</li>)}</ul></details>}
        {!!preview.preview.length&&<div className="table-scroll" role="region" aria-label="پیش‌نمایش ردیف‌های فایل" tabIndex={0}><table className="import-table"><thead><tr><th>تاریخ</th><th>شرح</th><th>شروع</th><th>پایان</th><th>دقیقه</th><th>وضعیت</th></tr></thead><tbody>{preview.preview.slice(0,10).map((r,i)=><tr key={i}><td><bdi dir="ltr">{r.date}</bdi></td><td>{r.title}</td><td>{fa(r.start||"—")}</td><td>{fa(r.end||"—")}</td><td>{fa(r.duration)}</td><td>{r.duplicate?"تکراری":"جدید"}</td></tr>)}</tbody></table></div>}
        {preview.preview.length>10&&<p className="hint">فقط ۱۰ ردیف نخست نمایش داده می‌شود؛ همهٔ ردیف‌ها بررسی شده‌اند.</p>}
      </>}
      <button className="btn btn-primary" disabled={busy||dirty||preview.error_count>0||preview.new_rows===0} onClick={()=>run(true)}>تأیید و واردکردن {fa(preview.new_rows)} تسک در حساب من</button>
    </div>}
  </section>;
}
