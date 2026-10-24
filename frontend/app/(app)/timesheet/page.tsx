"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { fa, fmtHM } from "@/lib/fa";
import { setDaylogDay } from "@/lib/daylog";
import { useTagColor } from "@/lib/data";
import { TimesheetData } from "@/lib/types";

export default function TimesheetPage() {
  const router = useRouter();
  const color = useTagColor();
  const [date, setDate] = useState<string | null>(null);   // any day inside the shown week; null = this week
  const { data } = useSWR<TimesheetData>("/api/timesheet" + (date ? `?date=${date}` : ""), fetcher);
  if (!data) return null;
  const first = data.days[0], last = data.days[6];
  const title = first.jalali_month === last.jalali_month
    ? `${fa(first.jalali_day)} تا ${fa(last.jalali_day)} ${last.month_name} ${fa(last.jalali_year)}`
    : `${fa(first.jalali_day)} ${first.month_name} تا ${fa(last.jalali_day)} ${last.month_name} ${fa(last.jalali_year)}`;

  return (
    <div className="card">
      <div className="daylog-nav">
        <button className="btn btn-outline" onClick={() => setDate(data.prev)}>◀ هفته قبل</button>
        <div><div className="jalali-big">{title}</div><div className="gregorian-line">مجموع هفته: {fmtHM(data.total)}</div></div>
        <button className="btn btn-outline" onClick={() => setDate(data.next)}>هفته بعد ▶</button>
      </div>
      <div className="shortcuts" style={{ marginTop: 10 }}><button className="btn btn-outline" onClick={() => setDate(null)}>این هفته</button></div>
      <details className="how-to">
        <summary>راهنما</summary>
        <ul>
          <li>هر ردیف یک تگ و هر ستون یک روز هفته (شنبه تا جمعه) است؛ داخل هر خانه جمع ساعت آن تگ در آن روز.</li>
          <li>ستون آخر جمع هفتگی هر تگ و ردیف آخر جمع هر روز است؛ برای انتقال سریع ساعت‌ها به سیستم شرکت.</li>
          <li>روی نام یک روز بزنید تا گزارش دقیقهٔ همان روز باز شود. عددها فقط خواندنی‌اند.</li>
        </ul>
      </details>
      {!data.rows.length ? <div className="empty-hint">در این هفته تسکی ثبت نشده است</div> : (
        <div className="ts-wrap">
          <table className="ts-table">
            <thead>
              <tr>
                <th className="ts-tag">تگ</th>
                {data.days.map((d) => (
                  <th key={d.gregorian} className={d.is_today ? "today" : ""}>
                    <button className="ts-day-btn" title="باز کردن گزارش روزانه" onClick={() => {
                      setDaylogDay({ year: d.jalali_year, month: d.jalali_month, day: d.jalali_day, gregorian: d.gregorian });
                      router.push("/daylog/");
                    }}>{d.weekday}<small>{fa(d.jalali_day)} {d.month_name}</small></button>
                  </th>
                ))}
                <th className="ts-total">جمع</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={String(r.tag_id)}>
                  <th className="ts-tag"><i className="sw" style={{ background: color(r.tag_id), marginInlineEnd: 6 }} />{r.tag_name}</th>
                  {r.minutes.map((m, i) => <td key={i} className={(m > 0 ? "" : "zero ") + (data.days[i].is_today ? "today" : "")}>{m > 0 ? fmtHM(m) : "—"}</td>)}
                  <td className="ts-total">{fmtHM(r.total)}</td>
                </tr>
              ))}
              <tr className="ts-foot">
                <th className="ts-tag">جمع روز</th>
                {data.day_totals.map((m, i) => <td key={i} className={data.days[i].is_today ? "today" : ""}>{m > 0 ? fmtHM(m) : "—"}</td>)}
                <td className="ts-total">{fmtHM(data.total)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
