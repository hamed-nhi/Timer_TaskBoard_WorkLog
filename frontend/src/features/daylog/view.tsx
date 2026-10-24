"use client";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { errorText, fetcher, get, post } from "@/lib/api";
import { fa, fmtDuration, gregorianLabel, MONTHS, weekdayOf } from "@/lib/format";
import { refreshAll, useCatalog, useTasks, useToday } from "@/lib/data";
import { DayRef, takeDaylogDay } from "@/features/daylog/navigation";
import { Catalog, EntryReportRow, FillSuggestion, Task } from "@/lib/types";
import { useTaskDialogs } from "@/features/tasks/components";
import { useFill } from "@/features/fill/components";
import { useUi } from "@/shared/ui";

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

/** A table cell (or card line) that copies its text when clicked. */
function Copyable({ text, show, className = "", tag = "td", children }: { text: string; show?: string; className?: string; tag?: "td" | "div"; children?: React.ReactNode }) {
  const [state, setState] = useState("");
  const Tag = tag as any;
  return (
    <Tag className={`copyable ${className} ${state}`} onClick={async () => {
      setState((await copyText(text)) ? "copied" : "copy-failed");
      setTimeout(() => setState(""), 900);
    }}>{children ?? show ?? text}</Tag>
  );
}

export default function DaylogPage() {
  const { data: today } = useToday();
  const { openEdit } = useTaskDialogs();
  const { openFill, rollback } = useFill();
  const { data: catalog } = useCatalog();
  const { toast } = useUi();
  const [day, setDay] = useState<DayRef | null>(null);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    if (day || !today) return;
    setDay(takeDaylogDay() || { year: today.jalali_year, month: today.jalali_month, day: today.jalali_day, gregorian: today.gregorian });
  }, [today]);

  const { data: tasks } = useTasks(day ? `year=${day.year}&month=${day.month}&day=${day.day}` : "");
  const { data: fill } = useSWR<FillSuggestion>(day ? `/api/fill-suggestion?date=${day.gregorian}` : null, fetcher);
  if (!day || !today) return null;

  async function shift(delta: number) {
    const n = await get(`/api/shift-date?year=${day!.year}&month=${day!.month}&day=${day!.day}&delta=${delta}`);
    setDay({ year: n.jalali_year, month: n.jalali_month, day: n.jalali_day, gregorian: n.gregorian });
  }

  const save = async (id: number, fields: Record<string, unknown>) => {
    try { await post(`/api/tasks/${id}/company`, fields); } catch (e) { toast(errorText(e)); }
    await refreshAll();
  };
  const entered = async (id: number, v: boolean) => { await post(`/api/tasks/${id}/entered`, { entered: v }); await refreshAll(); };

  const rows = (tasks || []).map((t) => {
    const raw = t.status === "done" ? t.duration_minutes : t.accumulated_minutes;
    const real = raw !== null && raw !== undefined ? Math.round(raw) : null;
    const fillMin = Math.round(t.fill_minutes || 0);
    return { t, real, fillMin, total: real === null ? null : real + fillMin };
  });
  const sumReal = rows.reduce((a, r) => a + (r.real || 0), 0);
  const sumFill = rows.reduce((a, r) => a + r.fillMin, 0);
  const hm = (m: number) => `${fa(Math.round(m))} دقیقه (${fmtDuration(m)})`;

  async function copyAll() {
    // tab-separated: pastes into Excel as columns (type, project, story, minutes, outside, planned, title, start, end)
    const text = rows.map(({ t, total }) => [t.company_type || "", t.company_project || "", t.company_story || "", String(total ?? "--"),
      t.outside_company ? "1" : "0", t.planned_flag ? "1" : "0", t.title, t.start_time || "", t.end_time || ""].join("\t")).join("\n");
    const ok = await copyText(text);
    setCopied(ok ? "کپی شد ✓" : "کپی نشد");
    setTimeout(() => setCopied(""), 1200);
  }

  const typeSelect = (t: Task) => <TypeSelect task={t} catalog={catalog} onChange={(id) => save(t.id, { report_type_id: id })} />;

  return (
    <>
      <div className="card">
        <div className="daylog-nav">
          <button className="btn btn-outline" onClick={() => shift(-1)}>◀ روز قبل</button>
          <div>
            <div className="jalali-big">{weekdayOf(day.gregorian)} {fa(`${day.year}/${String(day.month).padStart(2, "0")}/${String(day.day).padStart(2, "0")}`)}</div>
            <div className="gregorian-line">{gregorianLabel(day.gregorian)}</div>
          </div>
          <button className="btn btn-outline" onClick={() => shift(1)}>روز بعد ▶</button>
        </div>
        <div className="shortcuts" style={{ justifyContent: "center", marginTop: 14 }}>
          <button className="btn btn-outline" onClick={() => setDay({ year: today.jalali_year, month: today.jalali_month, day: today.jalali_day, gregorian: today.gregorian })}>برو به امروز</button>
          <button className="btn btn-outline" onClick={copyAll} title="نوع گزارش، پروژه، استوری، دقیقه، خارج از شرکت، پلن شده و شرح را برای چسباندن در اکسل کپی می‌کند">{copied || "کپی کل جدول"}</button>
          <button className="btn btn-outline" onClick={() => openFill(day.gregorian)}>تکمیل ساعت گزارش</button>
        </div>
        <div className="hint" style={{ marginTop: 12 }}>برای کپی، روی هر خانه‌ی جدول کلیک کنید (عنوان، ساعت‌ها یا دقیقه)؛ «کپی کل جدول» همه را یک‌جا برای اکسل کپی می‌کند.</div>
        <div className="hint">وقتی ساعت یک تسک را در سامانه اصلی شرکت هم ثبت کردید، تیکش را بزنید تا فراموش نشود کدام‌ها مانده.</div>

        {tasks && !tasks.length && <div className="empty-hint">تسکی برای این روز ثبت نشده</div>}
        {rows.length > 0 && (
          <>
            {/* wide screens: the table */}
            <div className="table-scroll daylog-table-wrap">
              <table className="daylog-table">
                <thead>
                  <tr>
                    <th>شرح فعالیت</th><th>نوع گزارش</th><th>نام پروژه</th><th>نام استوری</th><th>پلن شده</th><th>خارج از شرکت</th>
                    <th>شروع</th><th>پایان</th><th>ثبت شده</th><th>تکمیلی</th><th>دقیقه (برای سامانه اصلی)</th><th>ثبت در سامانه اصلی</th><th>ویرایش</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(({ t, real, fillMin, total }) => (
                    <tr key={t.id} className={t.entered_main_system ? "entered-row" : ""}>
                      <Copyable text={t.title} />
                      <td>{typeSelect(t)}</td>
                      <Copyable text={t.company_project || ""} show={t.company_project || "--"} />
                      <Copyable text={t.company_story || ""} show={t.company_story || "--"} />
                      <td><input type="checkbox" checked={t.planned_flag} aria-label="پلن شده" onChange={(e) => save(t.id, { planned_flag: e.target.checked })} /></td>
                      <td><input type="checkbox" checked={t.outside_company} aria-label="خارج از شرکت" onChange={(e) => save(t.id, { outside_company: e.target.checked })} /></td>
                      <Copyable text={t.start_time || ""} show={fa(t.start_time || "--")} />
                      <Copyable text={t.end_time || ""} show={t.end_time ? fa(t.end_time) : "..."} />
                      <Copyable text={String(real ?? "")} show={fa(real ?? "--")} />
                      <Copyable text={String(fillMin)} className="daylog-fill" show={fillMin ? "+" + fa(fillMin) : "—"} />
                      <Copyable text={String(total ?? "")}><span className="daylog-minutes-box">{fa(total ?? "--")} دقیقه</span></Copyable>
                      <td><input type="checkbox" checked={t.entered_main_system} onChange={(e) => entered(t.id, e.target.checked)} /></td>
                      <td><button className="icon-edit-btn" title="ویرایش این تسک" aria-label="ویرایش این تسک" onClick={() => openEdit(t)}>✎</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* phones: one card per task */}
            <div className="daylog-cards">
              {rows.map(({ t, real, fillMin, total }) => (
                <div key={t.id} className={"dl-card" + (t.entered_main_system ? " entered" : "")}>
                  <Copyable tag="div" className="dl-title" text={t.title} />
                  <div className="dl-meta">
                    <span>{fa(t.start_time || "--")} تا {t.end_time ? fa(t.end_time) : "..."}</span>
                    {t.company_project && <span>{t.company_project}</span>}
                    {t.company_story && <span>{t.company_story}</span>}
                  </div>
                  {typeSelect(t)}
                  <div className="dl-min">
                    <Copyable tag="div" text={String(total ?? "")}><span className="daylog-minutes-box">{fa(total ?? "--")} دقیقه</span></Copyable>
                    <span className="hint">ثبت شده {fa(real ?? "--")}</span>
                    {fillMin > 0 && <span className="dl-fill">+{fa(fillMin)} تکمیلی</span>}
                  </div>
                  <div className="dl-checks">
                    <label><input type="checkbox" checked={t.planned_flag} onChange={(e) => save(t.id, { planned_flag: e.target.checked })} /> پلن شده</label>
                    <label><input type="checkbox" checked={t.outside_company} onChange={(e) => save(t.id, { outside_company: e.target.checked })} /> خارج از شرکت</label>
                    <label><input type="checkbox" checked={t.entered_main_system} onChange={(e) => entered(t.id, e.target.checked)} /> ثبت شد در سامانه</label>
                  </div>
                  <button className="btn btn-outline btn-sm" onClick={() => openEdit(t)}>ویرایش ✎</button>
                </div>
              ))}
            </div>
            <div className="daylog-summary">
              <div className="daylog-sum-grid">
                <div><span>جمع ثبت شده</span><b>{hm(sumReal)}</b></div>
                <div className="sum-fill"><span>جمع تکمیلی</span><b>{hm(sumFill)}</b>
                  {sumFill > 0 && <button className="btn btn-outline fill-rollback-btn" onClick={() => rollback(day.gregorian)}>↶ برگرداندن به زمان ثبت‌شده</button>}
                </div>
                <div className="sum-report"><span>جمع برای سامانه‌ی اصلی</span><b>{hm(sumReal + sumFill)}</b></div>
                <div><span>حضور در شرکت</span><b>{fill && fill.presence_minutes ? fmtDuration(fill.presence_minutes) : "ثبت نشده"}</b></div>
              </div>
              {fill && fill.warnings.length > 0 && <div className="presence-note" style={{ marginTop: 8 }}>{fill.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>}
            </div>
          </>
        )}
      </div>
      <EntryReport />
    </>
  );
}

function TypeSelect({ task: t, catalog, onChange }: { task: Task; catalog?: Catalog; onChange: (id: number | null) => void }) {
  const auto = t.meeting_with ? "جلسات" : t.tag_report_type || "";
  return (
    <select aria-label="نوع گزارش" value={t.report_type_id ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{auto ? `${auto} (خودکار)` : "— انتخاب —"}</option>
      {catalog?.types.filter((x) => x.id).map((x) => <option key={x.id} value={x.id!}>{x.name}</option>)}
    </select>
  );
}

/** Which days still have hours not entered into the main system. */
function EntryReport() {
  const { data: today } = useToday();
  const [year, setYear] = useState<number | null>(null);
  const [month, setMonth] = useState<number | null>(null);
  const y = year ?? today?.jalali_year ?? 0;
  const m = month ?? today?.jalali_month ?? 1;
  const { data: rows } = useSWR<EntryReportRow[]>(today ? `/api/entry-report?year=${y}&month=${m}` : null, fetcher);
  const cur = today?.jalali_year || 0;
  return (
    <div className="card">
      <h2>گزارش روزهای ناقص (ساعتی که هنوز وارد سامانه اصلی نشده)</h2>
      <div className="filters">
        <select aria-label="سال" value={y} onChange={(e) => setYear(Number(e.target.value))}>{[cur - 2, cur - 1, cur, cur + 1].map((v) => <option key={v} value={v}>{fa(v)}</option>)}</select>
        <select aria-label="ماه" value={m} onChange={(e) => setMonth(Number(e.target.value))}>{MONTHS.map((n, i) => <option key={n} value={i + 1}>{n}</option>)}</select>
      </div>
      <div className="task-list">
        {rows && !rows.length && <div className="empty-hint">داده‌ای برای این ماه نیست</div>}
        {rows?.map((r) => (
          <div key={r.date} className={"entry-report-row " + (r.all_entered ? "complete" : "pending")}>
            <span>{fa(r.date)} · {fmtDuration(r.total_minutes)} · {fa(r.total_tasks)} تسک</span>
            <span className="entry-report-status">{r.all_entered ? "کامل ثبت شده ✓" : `${fa(r.total_tasks - r.entered_tasks)} مورد باقی‌مانده`}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
