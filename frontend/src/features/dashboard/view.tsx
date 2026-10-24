"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { fa, fmtDuration, fmtHM, fmtPercent, MONTHS } from "@/lib/format";
import { useTags, useTagColor, useToday } from "@/lib/data";
import { Comparison, Dashboard, TagSummary } from "@/lib/types";
import { BudgetBar, budgetText } from "@/shared/ui";
import { useTagActions } from "@/features/tags/components";

function delta(c: Comparison) {
  const up = c.diff_minutes > 0, down = c.diff_minutes < 0;
  return {
    arrow: up ? "▲" : down ? "▼" : "●", cls: up ? "up" : down ? "down" : "flat", up, down,
    amount: c.diff_percent !== null && c.diff_percent !== undefined ? fmtPercent(c.diff_percent) : fmtDuration(Math.abs(c.diff_minutes)),
  };
}

interface Col { label: string; title: string; value: number; active?: boolean; key?: number }

function ColumnChart({ items, goal, minCol = 20, showValues, onClick }: { items: Col[]; goal?: number; minCol?: number; showValues?: boolean; onClick?: (c: Col) => void }) {
  if (!items.length) return <div className="empty-hint">داده‌ای موجود نیست</div>;
  let max = Math.max(...items.map((i) => i.value), 1);
  const g = goal && goal <= max * 2 ? goal : null;
  if (g) max = Math.max(max, g);
  return (
    <div className="cc-scroll">
      <div style={{ minWidth: items.length * minCol }}>
        <div className="cc-plot">
          {g && <div className="cc-goal" style={{ bottom: `${(g / max) * 100}%` }}><span>هدف روزانه</span></div>}
          {items.map((c, i) => {
            const Tag: any = onClick ? "button" : "div";
            const title = `${c.title}: ${fmtDuration(c.value)}`;
            return (
              <Tag key={i} type={onClick ? "button" : undefined} className={"cc-col" + (c.active ? " active" : "") + (c.value === 0 ? " empty" : "")} title={title} aria-label={title}
                onClick={onClick ? () => onClick(c) : undefined}>
                <span className="cc-bar" style={{ height: `${c.value ? Math.max((c.value / max) * 100, 2) : 0}%` }}>
                  {showValues && c.value ? <span className="cc-v">{fmtHM(c.value)}</span> : null}
                </span>
              </Tag>
            );
          })}
        </div>
        <div className="cc-labels">{items.map((c, i) => <span key={i} className={c.active ? "active" : ""}>{fa(c.label)}</span>)}</div>
      </div>
    </div>
  );
}

function BarChart({ items, total, onClick }: { items: { label: string; value: number; color?: string; key?: number | string | null }[]; total?: number; onClick?: (k: number | string) => void }) {
  if (!items.length) return <div className="empty-hint">داده‌ای موجود نیست</div>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="bar-chart">
      {items.map((i, n) => {
        const clickable = onClick && i.key !== null && i.key !== undefined;
        return (
          <div key={n} className={"bar-row tag-row" + (clickable ? " clickable" : "")} role={clickable ? "button" : undefined} tabIndex={clickable ? 0 : undefined}
            title={clickable ? "نمایش جمع تجمعی این تگ" : undefined} onClick={clickable ? () => onClick!(i.key!) : undefined}
            onKeyDown={clickable ? (e) => (e.key === "Enter" || e.key === " ") && onClick!(i.key!) : undefined}>
            <div className="bar-label" title={i.label}><i className="sw" style={{ background: i.color || "var(--primary)" }} />{i.label}</div>
            <div className="bar-track"><div className="bar-fill" style={{ background: i.color, width: `${(i.value / max) * 100}%` }} /></div>
            <div className="bar-value">{fmtDuration(i.value)}{total ? <span className="bar-pct">{fmtPercent((i.value / total) * 100)}</span> : null}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const { data: today } = useToday();
  const { data: tags = [] } = useTags();
  const color = useTagColor();
  const { openManager } = useTagActions();
  const [year, setYear] = useState<number | null>(null);
  const [month, setMonth] = useState<number | "">("");
  const y = year ?? today?.jalali_year ?? 0;
  const { data } = useSWR<Dashboard>(today ? `/api/dashboard?year=${y}${month ? `&month=${month}` : ""}` : null, fetcher, { keepPreviousData: true });
  const [sumTag, setSumTag] = useState<string>("");
  const [range, setRange] = useState("all");
  const analysis = useRef<HTMLDivElement>(null);

  // first visit: start the cumulative card on the tag that took the most time
  useEffect(() => {
    if (!sumTag && data?.by_tag.length && data.by_tag[0].tag_id !== null) setSumTag(String(data.by_tag[0].tag_id));
  }, [data]);
  useEffect(() => { if (!month && range === "month") setRange("all"); }, [month]);

  if (!today || !data) return null;
  const cur = today.jalali_year;
  const c = data.comparison;
  const d = c ? delta(c) : null;

  const dayItems: Col[] = [];
  if (month) {
    const byDay = new Map(data.by_day.map((x) => [Number(x.date.split("/")[2]), x.minutes]));
    const len = data.days_in_month || 31;
    for (let n = 1; n <= Math.max(len, ...byDay.keys()); n++) dayItems.push({ label: String(n), title: `${fa(n)} ${MONTHS[Number(month) - 1]}`, value: byDay.get(n) || 0 });
  }
  const monthItems: Col[] = data.by_month.map((m) => {
    const no = Number(m.date.split("/")[1]);
    return { label: m.month_name, title: `${m.month_name} ${fa(y)}`, value: m.minutes, key: no, active: Number(month) === no };
  });
  const budgets = tags.filter((t) => t.budget_minutes);

  return (
    <>
      <div className="card">
        <div className="filters" style={{ marginBottom: 6 }}>
          <select aria-label="سال" value={y} onChange={(e) => setYear(Number(e.target.value))}>{[cur - 2, cur - 1, cur, cur + 1].map((v) => <option key={v} value={v}>{fa(v)}</option>)}</select>
          <select aria-label="ماه" value={month} onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}>
            <option value="">کل سال</option>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </select>
        </div>
        <div className="dash-period">{month ? `${MONTHS[Number(month) - 1]} ${fa(y)}` : `کل سال ${fa(y)}`}</div>
      </div>

      <div className="kpi-grid">
        <div className="stat-card kpi-main">
          <div className="stat-label">ساعت کار</div>
          <div className="stat-value dur">{fmtDuration(data.total_minutes)}</div>
          <div className={"kpi-delta " + (d?.cls || "")}>
            {c && d ? (c.diff_minutes === 0 ? `● برابر با ${c.label}` : `${d.arrow} ${d.amount} ${d.up ? "بیشتر" : "کمتر"} از ${c.label}${c.days ? ` (همان ${fa(c.days)} روز)` : ""}`) : ""}
          </div>
        </div>
        <div className="stat-card"><div className="stat-label">تعداد تسک</div><div className="stat-value">{fa(data.task_count)}</div></div>
        <div className="stat-card"><div className="stat-label">در حال انجام</div><div className="stat-value">{fa(data.running_count)}</div></div>
        <div className="stat-card"><div className="stat-label">مکث‌شده</div><div className="stat-value">{fa(data.paused_count)}</div></div>
      </div>

      <div className="card">
        <h2>مقایسه با دوره قبل</h2>
        <div className="hint">مقایسه همیشه بین بازه‌های هم‌اندازه است؛ مثلاً اگر ۱۰ روز از ماه گذشته، ۱۰ روز اول همین ماه با ۱۰ روز اول ماه قبل مقایسه می‌شود، نه با کل ماه قبل.</div>
        <div className="kpi-grid kpi-grid-3">
          <div className="stat-card">
            <div className="stat-label">{c ? `نسبت به ${c.label}` : "نسبت به دوره قبل"}</div>
            <div className={"stat-value dur " + (d?.cls || "")}>{c && d ? `${d.up ? "+" : d.down ? "−" : ""}${fmtDuration(Math.abs(c.diff_minutes))}` : "--"}</div>
            <div className={"stat-sub " + (d?.cls || "")}>
              {!c ? "برای این بازه مقایسه‌ای وجود ندارد" : c.diff_minutes === 0 ? "بدون تغییر" : c.diff_percent === null ? `${c.label}: کاری ثبت نشده` : `${d!.arrow} ${d!.amount} ${d!.up ? "بیشتر" : "کمتر"}`}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">میانگین ساعت کار روزانه</div>
            <div className="stat-value dur">{fmtDuration(data.avg_daily_minutes)}</div>
            <div className="stat-sub">{data.active_days ? `در ${fa(data.active_days)} روز فعال` : "روز فعالی نیست"}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">پرکارترین روز</div>
            <div className="stat-value dur">{data.best_day ? fmtDuration(data.best_day.minutes) : "--"}</div>
            <div className="stat-sub">{data.best_day ? fa(data.best_day.date) : ""}</div>
          </div>
        </div>
        {c && (
          <div className="bar-chart" style={{ marginTop: 14 }}>
            {[[c.current_label, c.current_minutes, "cur"], [c.prev_label, c.prev_minutes, "prev"]].map(([label, minutes, cls]) => {
              const max = Math.max(c.current_minutes, c.prev_minutes, 1);
              return (
                <div className="bar-row cmp-row" key={cls as string}>
                  <div className="bar-label">{fa(label as string)}</div>
                  <div className="bar-track"><div className={"bar-fill cmp-" + cls} style={{ width: `${((minutes as number) / max) * 100}%` }} /></div>
                  <div className="bar-value">{fmtDuration(minutes as number)}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className={"dash-grid" + (month ? "" : " single")}>
        {month ? <div className="card"><h2>ساعت کار به تفکیک روز</h2><ColumnChart items={dayItems} goal={data.daily_goal_minutes} minCol={18} /></div> : null}
        <div className="card">
          <h2>ساعت کار به تفکیک ماه</h2>
          <ColumnChart items={monthItems} showValues minCol={38} onClick={(col) => setMonth(col.key as number)} />
        </div>
      </div>

      <div className="card">
        <h2>ساعت کار به تفکیک تگ</h2>
        {data.total_minutes > 0 && (
          <div className="tag-share" aria-hidden="true">
            {data.by_tag.map((t, i) => <span key={i} style={{ width: `${(t.minutes / data.total_minutes) * 100}%`, background: color(t.tag_id) }} title={`${t.tag_name}: ${fmtDuration(t.minutes)}`} />)}
          </div>
        )}
        <div className="hint" style={{ margin: "10px 0" }}>هر تگ یک رنگ ثابت دارد. روی هر تگ بزنید تا جزئیات و جمع تجمعی‌اش در کارت پایین باز شود.</div>
        <BarChart total={data.total_minutes}
          items={data.by_tag.map((t) => ({ label: t.tag_name, value: t.minutes, color: color(t.tag_id), key: t.tag_id === null ? "none" : t.tag_id }))}
          onClick={(k) => { setSumTag(String(k)); analysis.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />
      </div>

      {budgets.length > 0 && (
        <div className="card">
          <h2>بودجه‌ی ساعت تگ‌ها</h2>
          <div className="hint" style={{ marginBottom: 10 }}>برای هر تگ در «ویرایش تگ‌ها» یک تخمین ساعت بگذارید؛ اینجا پیشرفتش دیده می‌شود.</div>
          <div className="budget-list">
            {budgets.map((t) => (
              <div key={t.id} className="budget-row clickable" onClick={() => { setSumTag(String(t.id)); analysis.current?.scrollIntoView({ behavior: "smooth" }); }}>
                <div className="budget-head"><span className="budget-name"><i className="sw" style={{ background: color(t.id) }} />{t.name}</span><span className="budget-text">{budgetText(t, fmtHM)}</span></div>
                <BudgetBar percent={t.budget_percent} />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card" ref={analysis}>
        <div className="section-head">
          <h2>زمان صرف‌شده روی یک تگ (تجمعی)</h2>
          <button className="btn btn-outline btn-sm" onClick={openManager}>ویرایش تگ‌ها ✎</button>
        </div>
        <div className="hint" style={{ margin: "8px 0 12px" }}>یک تگ را انتخاب کنید تا ببینید در مجموع چقدر روی آن وقت گذاشته‌اید. به‌طور پیش‌فرض کل زمان‌ها حساب می‌شود، نه فقط ماه یا سالی که بالا انتخاب کرده‌اید.</div>
        <div className="row2">
          <div>
            <label className="lbl">تگ</label>
            <select aria-label="تگ" value={sumTag} onChange={(e) => setSumTag(e.target.value)}>
              {tags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              <option value="none">(بدون تگ)</option>
            </select>
          </div>
          <div>
            <label className="lbl">بازه</label>
            <select aria-label="بازه" value={range} onChange={(e) => setRange(e.target.value)}>
              <option value="all">همه‌ی زمان‌ها (تجمعی)</option>
              <option value="year">فقط سال {fa(y)}</option>
              <option value="month" disabled={!month}>{month ? `فقط ${MONTHS[Number(month) - 1]} ${fa(y)}` : "فقط یک ماه (ماه را بالا انتخاب کنید)"}</option>
            </select>
          </div>
        </div>
        {sumTag && <TagSummaryView tag={sumTag} range={range} year={y} month={month} />}
      </div>
    </>
  );
}

function TagSummaryView({ tag, range, year, month }: { tag: string; range: string; year: number; month: number | "" }) {
  let url = `/api/tag-summary?tag=${encodeURIComponent(tag)}`;
  if (range !== "all") url += `&year=${year}`;
  if (range === "month" && month) url += `&month=${month}`;
  const { data } = useSWR<TagSummary>(url, fetcher, { keepPreviousData: true });
  if (!data) return null;
  const period = range === "all" ? "همه‌ی زمان‌ها" : range === "year" ? `سال ${fa(year)}` : `${MONTHS[Number(month) - 1]} ${fa(year)}`;
  return (
    <div style={{ marginTop: 12 }}>
      {data.budget && (
        <div className="stack" style={{ marginBottom: 12 }}>
          <div className="tag-sub-title" style={{ margin: 0 }}>پیشرفت بودجه‌ی ساعت</div>
          <BudgetBar percent={data.budget.budget_percent} />
          <div className="budget-text">{budgetText(data.budget, fmtHM)}</div>
        </div>
      )}
      {!data.task_count ? <div className="empty-hint">برای «{data.tag.name}» در {period} تسک تمام‌شده‌ای ثبت نشده</div> : (
        <>
          <div className="tag-stat-grid">
            <div className="stat-card stat-card-wide"><div className="stat-value dur">{fmtDuration(data.total_minutes)}</div><div className="stat-label">کل زمان «{data.tag.name}»</div>
              <div className="stat-sub">{fa(Math.round(data.total_minutes / 6) / 10)} ساعت · {fa(Math.round(data.total_minutes))} دقیقه</div></div>
            <div className="stat-card"><div className="stat-value dur">{fa(data.task_count)}</div><div className="stat-label">تعداد تسک</div></div>
            <div className="stat-card"><div className="stat-value dur">{fa(data.day_count)}</div><div className="stat-label">روز دارای فعالیت</div></div>
            <div className="stat-card"><div className="stat-value dur">{fmtDuration(data.avg_per_day_minutes)}</div><div className="stat-label">میانگین در هر روز فعال</div></div>
          </div>
          <div className="hint">بازه‌ی فعالیت: از {fa(data.first_date)} تا {fa(data.last_date)} · {period}</div>
          {data.by_month.length > 1 && (<><div className="tag-sub-title">به تفکیک ماه</div><BarChart items={data.by_month.map((m) => ({ label: `${m.month_name} ${fa(m.date.split("/")[0])}`, value: m.minutes }))} /></>)}
          {data.top_titles.length > 0 && (
            <>
              <div className="tag-sub-title">عنوان‌هایی که بیشترین زمان را گرفته‌اند</div>
              {data.top_titles.map((t) => <div className="tag-title-row" key={t.title}><span>{t.title}</span><span className="tag-title-time">{fmtDuration(t.minutes)}{t.count > 1 ? ` · ${fa(t.count)} بار` : ""}</span></div>)}
            </>
          )}
        </>
      )}
      {data.recent.length > 0 && (
        <>
          <div className="tag-sub-title">آخرین کارهای انجام‌شده</div>
          {data.recent.map((t, i) => <div className="tag-title-row" key={i}><span>{fa(t.date)}  {t.title}</span><span className="tag-title-time">{fmtDuration(t.minutes)}</span></div>)}
        </>
      )}
      {data.open_count > 0 && <div className="hint" style={{ color: "#92400e", marginTop: 12 }}>{fa(data.open_count)} تسک این تگ هنوز باز است (تا الان {fmtDuration(data.open_minutes)}) و تا وقتی تمام نشود در جمع بالا حساب نمی‌شود.</div>}
    </div>
  );
}
