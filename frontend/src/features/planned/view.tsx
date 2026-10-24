"use client";
import { useEffect, useState } from "react";
import { errorText, post } from "@/lib/api";
import { refreshAll, usePlanned, useToday } from "@/lib/data";
import { GregHint, nextJalaliDay, PlannedRow } from "@/features/tasks/components";
import { TagSelect } from "@/features/tags/components";
import { DatePicker, useUi, YMD } from "@/shared/ui";

export default function PlannedPage() {
  const { data: today } = useToday();
  const { data: items } = usePlanned();
  const { toast } = useUi();
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState<number | null>(null);
  const [date, setDate] = useState<YMD>({ year: 0, month: 1, day: 1 });

  useEffect(() => {
    if (!today || date.year) return;
    // the calendar can hand over a day ("plan for this day")
    let chosen: YMD | null = null;
    try {
      const raw = sessionStorage.getItem("plannedDay");
      if (raw) { chosen = JSON.parse(raw); sessionStorage.removeItem("plannedDay"); }
    } catch { /* ignore */ }
    setDate(chosen || { year: today.jalali_year, month: today.jalali_month, day: today.jalali_day });
  }, [today]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      await post("/api/planned", { title: title.trim(), jalali_year: date.year, jalali_month: date.month, jalali_day: date.day, tag_id: tag });
    } catch (err) { return toast(errorText(err)); }
    setTitle(""); setTag(null);
    await refreshAll();
  }

  return (
    <>
      <div className="card">
        <h2>افزودن تسک برنامه‌ریزی‌شده</h2>
        <form className="stack" onSubmit={add}>
          <input type="text" aria-label="شرح فعالیت برنامه‌ریزی‌شده" placeholder="مثلا: تحویل گزارش ماهانه" required value={title} onChange={(e) => setTitle(e.target.value)} />
          <div><label className="lbl">عنوان استوری</label><TagSelect value={tag} onChange={setTag} /></div>
          <DatePicker value={date} onChange={setDate} />
          <GregHint date={date} />
          <div className="shortcuts">
            <button type="button" className="btn btn-outline" onClick={() => today && setDate({ year: today.jalali_year, month: today.jalali_month, day: today.jalali_day })}>امروز</button>
            <button type="button" className="btn btn-outline" onClick={async () => today && setDate(await nextJalaliDay({ year: today.jalali_year, month: today.jalali_month, day: today.jalali_day }))}>فردا</button>
          </div>
          <button type="submit" className="btn btn-primary">افزودن به برنامه ▶</button>
        </form>
      </div>
      <div className="card">
        <h2>لیست تسک‌های برنامه‌ریزی‌شده</h2>
        <div className="hint" style={{ marginBottom: 10 }}>
          هر وقت خواستید شروعِ واقعی‌اش کنید، روی «شروع» بزنید — یک تسک زنده برای همین الان ساخته می‌شود و از این لیست حذف می‌شود. مواردی که تاریخشان گذشته و هنوز کاری برایشان نکرده‌اید با رنگ قرمز مشخص شده‌اند؛ با «انتقال به فردا» یا «ویرایش» می‌توانید تاریخشان را عوض کنید.
        </div>
        <div className="task-list">
          {items?.length ? items.map((p) => <PlannedRow key={p.id} p={p} />) : <div className="empty-hint">هنوز تسکی برنامه‌ریزی نکرده‌اید</div>}
        </div>
      </div>
    </>
  );
}
