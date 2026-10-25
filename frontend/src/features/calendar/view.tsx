"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { fa, fmtDuration, gregorianLabel, latin, MONTHS, WEEKDAYS, WEEKDAYS_SHORT } from "@/lib/format";
import { setDaylogDay } from "@/features/daylog/navigation";
import { useToday } from "@/lib/data";
import { CalendarDay, CalendarEvent, CalendarMonth } from "@/lib/types";
import { useTaskDialogs } from "@/features/tasks/components";

const PREVIEW = 5;

export default function CalendarPage() {
  const router = useRouter();
  const { data: today } = useToday();
  const { openEdit } = useTaskDialogs();
  const [ym, setYm] = useState<{ year: number; month: number } | null>(null);
  const [selected, setSelected] = useState(1);
  const [world, setWorld] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [yearText, setYearText] = useState("");

  useEffect(() => {
    try { setWorld(localStorage.getItem("calWorld") !== "0"); } catch { /* default on */ }
  }, []);
  useEffect(() => {
    if (today && !ym) { setYm({ year: today.jalali_year, month: today.jalali_month }); setSelected(today.jalali_day); }
  }, [today]);
  useEffect(() => { if (ym) setYearText(String(ym.year)); }, [ym?.year]);

  const { data } = useSWR<CalendarMonth>(ym ? `/api/calendar?year=${ym.year}&month=${ym.month}` : null, fetcher, { keepPreviousData: true });
  useEffect(() => { setExpanded(false); }, [ym?.year, ym?.month]);
  if (!ym || !today || !data) return null;

  const go = (year: number, month: number, day = 1) => { setYm({ year, month }); setSelected(day); };
  const shift = (delta: number) => {
    let y = ym.year, m = ym.month + delta;
    if (m > 12) { m = 1; y += 1; }
    if (m < 1) { m = 12; y -= 1; }
    go(y, m);
  };
  const visible = (d: CalendarDay) => d.events.filter((e) => e.kind !== "world" || world);
  const sel = data.days.find((d) => d.day === Math.min(selected, data.days_in_month)) || data.days[0];
  const isThisMonth = data.jalali_year === today.jalali_year && data.jalali_month === today.jalali_month;
  const approx = data.days.some((d) => !d.hijri.exact || d.events.some((e) => e.approx));

  const eventRows: { day: CalendarDay; e: CalendarEvent }[] = [];
  data.days.forEach((d) => visible(d).forEach((e) => eventRows.push({ day: d, e })));
  const shown = expanded ? eventRows : eventRows.slice(0, PREVIEW);

  return (
    <div className="calendar-workspace">
      <div className="card">
        <div className="cal-head">
          <button className="btn btn-outline" onClick={() => shift(-1)}>◀ ماه قبل</button>
          <div className="cal-title">
            <div className="jalali-big">{fa(sel.day)} {data.month_name} {fa(data.jalali_year)}</div>
            <div className="gregorian-line">{WEEKDAYS[sel.weekday]} · <bdi dir="ltr">{gregorianLabel(sel.gregorian)}</bdi></div>
            <div className="gregorian-line">قمری: {fa(sel.hijri.day)} {sel.hijri.month_name} {fa(sel.hijri.year)}{sel.hijri.exact ? "" : " (تقریبی)"}</div>
          </div>
          <button className="btn btn-outline" onClick={() => shift(1)}>ماه بعد ▶</button>
        </div>
        <div className="cal-tools">
          <select aria-label="ماه" value={ym.month} onChange={(e) => go(ym.year, Number(e.target.value))}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
          <input type="text" inputMode="numeric" aria-label="سال" maxLength={4} value={fa(yearText)} onChange={(e) => setYearText(latin(e.target.value).replace(/\D/g, ""))}
            onBlur={() => { const y = Number(yearText); if (y >= 1 && y <= 3000) go(y, ym.month); else setYearText(String(ym.year)); }}
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
          <button className="btn btn-outline btn-sm" onClick={() => go(today.jalali_year, today.jalali_month, today.jalali_day)}>برو به امروز</button>
          <label className="cal-toggle"><input type="checkbox" checked={world} onChange={(e) => {
            setWorld(e.target.checked);
            try { localStorage.setItem("calWorld", e.target.checked ? "1" : "0"); } catch { /* ignore */ }
          }} /> مناسبت‌های جهانی</label>
        </div>
        <div className="cal-grid" role="group" aria-label="تقویم ماه">
          {WEEKDAYS_SHORT.map((w, i) => <div key={w} className={"cal-wd" + (i === 6 ? " friday" : "")} title={WEEKDAYS[i]}>{w}</div>)}
          {Array.from({ length: data.first_weekday }, (_, i) => <div key={"p" + i} />)}
          {data.days.map((d) => {
            const ev = visible(d);
            const g = d.gregorian.split("-").map(Number);
            const holiday = d.holiday || d.weekday === 6;
            const cls = "cal-cell" + (holiday ? " holiday" : "") + (isThisMonth && d.day === today.jalali_day ? " today" : "") + (d.day === sel.day ? " selected" : "");
            return (
              <div key={d.day} className={cls} onClick={() => setSelected(d.day)}
                title={[`${WEEKDAYS[d.weekday]} ${fa(d.day)} ${data.month_name}`, ...ev.slice(0, 3).map((e) => e.title)].join("\n")}>
                <button type="button" className="cal-day cal-day-button" aria-pressed={d.day === sel.day} aria-label={`${WEEKDAYS[d.weekday]} ${fa(d.day)} ${data.month_name} ${fa(data.jalali_year)}؛ میلادی ${fa(g[2])}/${fa(g[1])}/${fa(g[0])}؛ قمری ${fa(d.hijri.day)} ${d.hijri.month_name}`}>{fa(d.day)}</button>
                <span className="cal-g" dir="rtl" aria-hidden="true">{g[2] === 1 ? `${fa(1)} / ${fa(g[1])}` : fa(g[2])}</span>
                <span className="cal-h" aria-hidden="true">{d.hijri.day === 1 ? `${fa(1)} ${d.hijri.month_name}` : fa(d.hijri.day)}</span>
                <span className="cal-dots">
                  {ev.some((e) => e.holiday) && <i className="dot dot-holiday" />}
                  {ev.some((e) => !e.holiday) && <i className="dot dot-event" />}
                  {d.task_count > 0 && <i className="dot dot-work" />}
                  {d.planned_count > 0 && <i className="dot dot-plan" />}
                </span>
              </div>
            );
          })}
        </div>
        <div className="cal-legend">
          <span><i className="lg" style={{ background: "#ef4444" }} />تعطیل</span>
          <span><i className="lg" style={{ background: "#6366f1" }} />مناسبت</span>
          <span><i className="lg" style={{ background: "#10b981" }} />تسک ثبت‌شده</span>
          <span><i className="lg" style={{ background: "#f59e0b" }} />برنامه‌ریزی‌شده</span>
        </div>
        {approx && <div className="hint" style={{ marginTop: 8 }}>تاریخ مناسبت‌های قمری این ماه محاسبه‌ای است و ممکن است یک روز با اعلام رسمی تفاوت داشته باشد (برای سال‌های ۱۴۰۴ تا ۱۴۰۸ تاریخ‌ها دقیق و رسمی‌اند).</div>}
      </div>

      <div className="card">
        <div className="cal-detail-title">{WEEKDAYS[sel.weekday]} {fa(sel.day)} {data.month_name} {fa(data.jalali_year)}</div>
        <div className="cal-detail-sub">میلادی: <bdi dir="ltr">{gregorianLabel(sel.gregorian)}</bdi></div>
        <div className="cal-detail-sub">قمری: {fa(sel.hijri.day)} {sel.hijri.month_name} {fa(sel.hijri.year)}{sel.hijri.exact ? "" : " (تقریبی)"}</div>
        <div className="cal-detail-events">
          {sel.weekday === 6 && <div className="cal-event holiday"><span className="cal-event-tag">تعطیل</span>جمعه (تعطیل هفتگی)</div>}
          {visible(sel).map((e, i) => (
            <div key={i} className={"cal-event" + (e.holiday ? " holiday" : "") + (e.kind === "world" ? " world" : "")}>
              {e.holiday && <span className="cal-event-tag">تعطیل</span>}{e.title}{e.approx ? " (تقریبی)" : ""}
            </div>
          ))}
          {!visible(sel).length && sel.weekday !== 6 && <div className="hint">برای این روز مناسبتی ثبت نشده</div>}
        </div>
        <div className="cal-detail-work">
          {sel.task_count || sel.planned_count
            ? [sel.task_count ? `${fa(sel.task_count)} تسک ثبت‌شده · ${fmtDuration(sel.minutes)}` : "", sel.planned_count ? `${fa(sel.planned_count)} مورد برنامه‌ریزی‌شده` : ""].filter(Boolean).join(" — ")
            : "برای این روز چیزی ثبت یا برنامه‌ریزی نشده"}
        </div>
        <div className="cal-detail-actions">
          {sel.task_count > 0 && (
            <button className="btn btn-outline" onClick={() => {
              setDaylogDay({ year: data.jalali_year, month: data.jalali_month, day: sel.day, gregorian: sel.gregorian });
              router.push("/daylog/");
            }}>مشاهده در گزارش روزانه</button>
          )}
          <button className="btn btn-outline" onClick={() => {
            try { sessionStorage.setItem("plannedDay", JSON.stringify({ year: data.jalali_year, month: data.jalali_month, day: sel.day })); } catch { /* ignore */ }
            router.push("/planned/");
          }}>برنامه‌ریزی برای این روز</button>
          <button className="btn btn-outline" onClick={() => openEdit(null, { year: data.jalali_year, month: data.jalali_month, day: sel.day })}>ثبت تسک برای این روز</button>
        </div>
      </div>

      <div className="card">
        <h2>مناسبت‌ها و تعطیلات {data.month_name} {fa(data.jalali_year)}</h2>
        <div className="cal-events">
          {!eventRows.length && <div className="empty-hint">مناسبتی برای این ماه ثبت نشده</div>}
          {shown.map(({ day, e }, i) => {
            const g = day.gregorian.split("-").map(Number);
            return (
              <button key={i} type="button" className={"cal-event-row" + (e.holiday ? " holiday" : "")} onClick={() => setSelected(day.day)}>
                <span className="cal-event-date">{fa(day.day)}</span>
                <span className="cal-event-text">{e.title}{e.approx ? " (تقریبی)" : ""}</span>
                {e.kind === "world" && <span className="cal-event-note"><bdi dir="ltr">{fa(g[2])} / {fa(g[1])}</bdi></span>}
              </button>
            );
          })}
        </div>
        {eventRows.length > PREVIEW && (
          <button className="btn btn-outline" style={{ width: "100%", marginTop: 10 }} aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
            {expanded ? "نمایش کمتر ▴" : `نمایش ${fa(eventRows.length - PREVIEW)} مورد دیگر ▾`}
          </button>
        )}
      </div>
    </div>
  );
}
