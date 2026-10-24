"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { mutate } from "swr";
import useSWR from "swr";
import { errorText, fetcher, post } from "@/lib/api";
import { fa, fmtDuration, fmtHM, gregorianLabel, weekdayOf } from "@/lib/fa";
import { refreshAll, serverClock, serverNow, useClock, useGoals, usePlanned, useSettings, useTags, useTasks, useToday } from "@/lib/data";
import { PresenceCard } from "@/components/presence";
import { PlannedRow, TaskRow, useConfirmLongSpan } from "@/components/tasks";
import { TagSelect } from "@/components/tags";
import { BudgetBar, budgetText, Modal, NumInput, TimeInput, useUi } from "@/components/ui";
import { describe } from "@/lib/span";

export default function TodayPage() {
  const { data: today } = useToday();
  const now = useClock();
  const q = today ? `year=${today.jalali_year}&month=${today.jalali_month}&day=${today.jalali_day}` : "";
  const { data: tasks } = useTasks(q);

  // the page is often left open overnight: when the date changes, "today" must follow
  useEffect(() => {
    if (!today) return;
    const d = serverNow(now);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    if (key !== today.gregorian) mutate("/api/today");
  }, [now]);

  if (!today) return null;
  const active = (tasks || []).filter((t) => t.status !== "done");
  const done = (tasks || []).filter((t) => t.status === "done");
  const clock = serverNow(now).toLocaleTimeString("fa-IR", { hour12: false });

  return (
    <>
      <PresenceCard />
      <GoalsCard />
      <PlanReminder />

      <div className="card card-now">
        <span className="section-pill"><span className="live-dot" /> همین الان</span>
        <div className="today-date">
          <div>
            <div className="jalali-big">{weekdayOf(today.gregorian)} {fa(today.jalali_day)} {today.month_name} {fa(today.jalali_year)}</div>
            <div className="gregorian-line">{gregorianLabel(today.gregorian)}</div>
          </div>
          <div className="clock">{clock}</div>
        </div>
        <QuickStart />
      </div>

      <div className="card card-running">
        <h2>تسک‌های در حال انجام / مکث‌شده</h2>
        <div className="task-list">
          {active.length ? active.map((t) => <TaskRow key={t.id} task={t} />) : <div className="empty-hint">تسک در حال انجام یا مکث‌شده‌ای نیست</div>}
        </div>
      </div>

      <div className="card card-done">
        <h2>تسک‌های امروز</h2>
        <div className="task-list">
          {done.length ? done.map((t) => <TaskRow key={t.id} task={t} reopenable />) : <div className="empty-hint">هنوز تسکی برای امروز ثبت نشده</div>}
        </div>
      </div>
    </>
  );
}

/* ---------- goals ---------- */

function GoalsCard() {
  const { data: g } = useGoals();
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState(false);
  useEffect(() => { try { setOpen(localStorage.getItem("goalsOpen") === "1"); } catch { /* collapsed */ } }, []);
  if (!g) return null;
  const pct = g.daily_goal_minutes > 0 ? Math.round((g.today_minutes / g.daily_goal_minutes) * 100) : 0;
  const bar = (m: number, goal: number) => `${goal > 0 ? Math.min(100, (m / goal) * 100).toFixed(1) : 0}%`;
  return (
    <details className="card goals-card" open={open} onToggle={(e) => {
      const o = (e.target as HTMLDetailsElement).open;
      setOpen(o);
      try { localStorage.setItem("goalsOpen", o ? "1" : "0"); } catch { /* ignore */ }
    }}>
      <summary>
        <span className="goals-title">هدف امروز و این هفته</span>
        <span className="goal-summary-chip">امروز {fa(pct)}٪ · {fmtDuration(g.today_minutes)}</span>
        <span className="goals-chevron" aria-hidden="true">▾</span>
      </summary>
      <div className="goals-body">
        <div className="hint">این معیار سریع نشون می‌ده امروز و این هفته چقدر از هدف ساعت کاری‌تون رو پر کردید.</div>
        <div className="goal-row">
          <div className="goal-label"><span>امروز</span><span>{fmtDuration(g.today_minutes)} از {fmtDuration(g.daily_goal_minutes)}</span></div>
          <div className="bar-track goal-track"><div className="bar-fill" style={{ width: bar(g.today_minutes, g.daily_goal_minutes) }} /></div>
        </div>
        <div className="goal-row">
          <div className="goal-label"><span>این هفته</span><span>{fmtDuration(g.week_minutes)} از {fmtDuration(g.weekly_goal_minutes)}</span></div>
          <div className="bar-track goal-track"><div className="bar-fill" style={{ width: bar(g.week_minutes, g.weekly_goal_minutes) }} /></div>
        </div>
        <button className="btn btn-outline btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => setEdit(true)}>تنظیم هدف ساعت کاری ⚙</button>
      </div>
      {edit && <GoalsDialog onClose={() => setEdit(false)} />}
    </details>
  );
}

function GoalsDialog({ onClose }: { onClose: () => void }) {
  const { data: s } = useSettings();
  const [daily, setDaily] = useState("");
  const [weekly, setWeekly] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { if (s) { setDaily(String(s.daily_goal_minutes)); setWeekly(String(s.weekly_goal_minutes)); } }, [s]);
  async function save() {
    if (!Number(daily) || !Number(weekly)) return;
    try { await post("/api/settings", { daily_goal_minutes: Number(daily), weekly_goal_minutes: Number(weekly) }); } catch (e) { return setError(errorText(e)); }
    onClose();
    await refreshAll();
  }
  return (
    <Modal onClose={onClose}>
      <h2>تنظیم هدف ساعت کاری</h2>
      <label className="lbl">هدف روزانه (دقیقه)</label>
      <NumInput label="هدف روزانه" value={daily} onChange={setDaily} />
      <label className="lbl">هدف هفتگی (دقیقه)</label>
      <NumInput label="هدف هفتگی" value={weekly} onChange={setWeekly} />
      <div className="form-error">{error}</div>
      <div className="modal-actions"><div className="spacer" /><button className="btn btn-outline" onClick={onClose}>انصراف</button><button className="btn btn-primary" onClick={save}>ذخیره</button></div>
    </Modal>
  );
}

/* ---------- planned for today ---------- */

function PlanReminder() {
  const { data: today } = useToday();
  const { data: all = [] } = usePlanned();
  const planned = all.filter((p) => p.gregorian === today?.gregorian);
  const overdue = all.filter((p) => p.overdue);
  if (!planned.length && !overdue.length) return null;
  return (
    <div className="card plan-reminder-card">
      <h2>برای امروز از قبل برنامه‌ریزی کرده بودید <span className="plan-count">{fa(planned.length)}</span></h2>
      <div className="task-list">
        {planned.length ? planned.map((p) => <PlannedRow key={p.id} p={p} />) : <div className="empty-hint">برای امروز مورد جدیدی نیست</div>}
      </div>
      {overdue.length > 0 && (
        <Link href="/planned/" className="plan-overdue-strip" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
          ⚠ {fa(overdue.length)} برنامه‌ی عقب‌افتاده دارید که روزش گذشته — مشاهده و جابه‌جایی
        </Link>
      )}
    </div>
  );
}

/* ---------- quick start ---------- */

function QuickStart() {
  const { toast } = useUi();
  const confirmLong = useConfirmLongSpan();
  const { data: tags = [] } = useTags();
  const { data: titles = [] } = useSWR<string[]>("/api/yesterday-titles", fetcher);
  const now = useClock();
  const [title, setTitle] = useState("");
  const [tag, setTag] = useState<number | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [start, setStart] = useState("");
  const [auto, setAuto] = useState(true);       // the start shows "now" until the user types their own time
  const [end, setEnd] = useState("");
  const [bad, setBad] = useState(false);
  const [busy, setBusy] = useState(false);

  // the pre-filled "now" goes stale, so it is refreshed until the user types their own time
  useEffect(() => { if (advanced && auto) setStart(serverClock(now)); }, [advanced, auto, Math.floor(now / 15000)]);

  const selected = tags.find((t) => t.id === tag);
  const bits = selected ? [selected.report_type, selected.project].filter(Boolean) : [];
  const info = describe(start, end, bad);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || busy) return;
    if (bad) return toast("ساعت نامعتبر است (فرمت درست مثل ۰۹:۳۰)");
    // an untouched, pre-filled start means "now": let the server use the real moment of submitting
    const payload: Record<string, unknown> = { title: title.trim() };
    if (start && !(auto && !end)) payload.start_time = start;
    if (end) payload.end_time = end;
    if (tag) payload.tag_id = tag;
    if (payload.start_time && end && !(await confirmLong(payload.start_time as string, end))) return;
    setBusy(true);
    try {
      await post("/api/tasks", payload);
    } catch (err) { toast(errorText(err)); setBusy(false); return; }
    setTitle(""); setStart(""); setEnd(""); setAuto(true); setAdvanced(false); setBusy(false);
    await refreshAll();
    mutate("/api/yesterday-titles");
  }

  return (
    <form className="stack" onSubmit={submit}>
      <input type="text" list="yesterdayTitles" aria-label="شرح فعالیت" placeholder="شرح فعالیت... (مثلا: جلسه تیم، توسعه فلان قابلیت)" required
        value={title} onChange={(e) => setTitle(e.target.value)} />
      <datalist id="yesterdayTitles">{titles.map((t) => <option key={t} value={t} />)}</datalist>
      <div>
        <label className="lbl">عنوان استوری</label>
        <TagSelect value={tag} onChange={setTag} />
        {bits.length > 0 && <div className="tag-company-line">{bits.join(" · ")}</div>}
        {selected?.budget_minutes ? (
          <div className="quick-budget">
            <BudgetBar percent={selected.budget_percent} />
            <div className="budget-text">بودجه‌ی «{selected.name}»: {budgetText(selected, fmtHM)}</div>
          </div>
        ) : null}
      </div>
      <button type="button" className="btn btn-link" style={{ alignSelf: "flex-start" }} onClick={() => setAdvanced(!advanced)}>
        زمان سفارشی {advanced ? "▴" : "▾"}
      </button>
      {advanced && (
        <div className="stack" style={{ background: "#f8f9fd", borderRadius: 10, padding: 12 }}>
          <div className="row2">
            <div>
              <label className="lbl">ساعت شروع</label>
              <TimeInput label="ساعت شروع" value={start} onChange={(v) => { setStart(v); setAuto(false); }} onInvalid={setBad} />
            </div>
            <div>
              <label className="lbl">ساعت پایان (اختیاری)</label>
              <TimeInput label="ساعت پایان" value={end} onChange={setEnd} placeholder="۱۰:۳۰" onInvalid={setBad} />
            </div>
          </div>
          <div className={"span-preview " + info.level} aria-live="polite">{info.text}</div>
          <div className="hint">اگر ساعت پایان را خالی بگذارید، تسک «در حال انجام» شروع می‌شود و می‌توانید بعدا آن را متوقف یا مکث کنید.</div>
        </div>
      )}
      <button type="submit" className="btn btn-primary" disabled={busy}>ثبت تسک ▶</button>
    </form>
  );
}
