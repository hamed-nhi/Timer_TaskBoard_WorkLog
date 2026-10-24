"use client";
import { useState } from "react";
import { fa, fmtDuration, MONTHS } from "@/lib/format";
import { useTasks, useToday } from "@/lib/data";
import { Task } from "@/lib/types";
import { TaskRow, useTaskDialogs } from "@/features/tasks/components";

export default function AllTasksPage() {
  const { data: today } = useToday();
  const { openEdit } = useTaskDialogs();
  const [year, setYear] = useState<number | null>(null);
  const [month, setMonth] = useState<number | null | "">(null);
  const y = year ?? today?.jalali_year ?? 0;
  const m = month === null ? today?.jalali_month ?? "" : month;
  const { data: tasks } = useTasks(today ? `year=${y}${m ? `&month=${m}` : ""}` : "");

  const groups = new Map<string, Task[]>();
  (tasks || []).forEach((t) => groups.set(t.jalali_date_str, [...(groups.get(t.jalali_date_str) || []), t]));
  const dates = [...groups.keys()].sort().reverse();
  const cur = today?.jalali_year || 0;

  return (
    <div className="card">
      <div className="filters">
        <select aria-label="سال" value={y} onChange={(e) => setYear(Number(e.target.value))}>
          {[cur - 2, cur - 1, cur, cur + 1].map((v) => <option key={v} value={v}>{fa(v)}</option>)}
        </select>
        <select aria-label="ماه" value={m} onChange={(e) => setMonth(e.target.value ? Number(e.target.value) : "")}>
          <option value="">همه ماه‌ها</option>
          {MONTHS.map((n, i) => <option key={n} value={i + 1}>{n}</option>)}
        </select>
        <button className="btn" onClick={() => openEdit(null)}>+ افزودن تسک برای هر تاریخی</button>
        <a className="btn btn-outline" href={`/api/export?year=${y}`} style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}>دریافت خروجی اکسل ⬇</a>
      </div>
      <div className="task-list">
        {!tasks?.length && <div className="empty-hint">{tasks ? "تسکی یافت نشد" : "..."}</div>}
        {dates.map((d) => (
          <div key={d} className="task-list">
            <div className="date-group-header">
              <span>{fa(d)}</span>
              <span className="date-group-total">{fmtDuration(groups.get(d)!.reduce((s, t) => s + (t.duration_minutes || 0), 0))}</span>
            </div>
            {groups.get(d)!.map((t) => <TaskRow key={t.id} task={t} deletable />)}
          </div>
        ))}
      </div>
    </div>
  );
}
