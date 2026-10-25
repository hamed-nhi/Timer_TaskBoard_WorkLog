"use client";
import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";
import { del, errorText, get, post, put } from "@/lib/api";
import { fa, fmtDuration, gregorianLabel, latin, spanMinutes } from "@/lib/format";
import { liveMinutes, refreshAll, serverNow, useClock, useTagColor, useToday } from "@/lib/data";
import { Planned, Segment, Task } from "@/lib/types";
import { DatePicker, MoreMenu, Modal, TimeInput, useUi, YMD } from "@/shared/ui";
import { TagSelect } from "@/features/tags/components";

/* ---------- dialogs shared by every page ---------- */

interface TaskCtx {
  openEdit: (task: Task | null, preset?: YMD) => void;
  openSegments: (task: Task) => void;
  openPlannedEdit: (p: Planned) => void;
}
const Ctx = createContext<TaskCtx>({ openEdit: () => {}, openSegments: () => {}, openPlannedEdit: () => {} });
export const useTaskDialogs = () => useContext(Ctx);

export function TaskDialogsProvider({ children }: { children: ReactNode }) {
  const [edit, setEdit] = useState<{ task: Task | null; preset?: YMD } | null>(null);
  const [segments, setSegments] = useState<Task | null>(null);
  const [planned, setPlanned] = useState<Planned | null>(null);
  return (
    <Ctx.Provider value={{
      openEdit: (task, preset) => setEdit({ task, preset }),
      openSegments: setSegments,
      openPlannedEdit: setPlanned,
    }}>
      {children}
      {edit && <EditTaskDialog task={edit.task} preset={edit.preset} onClose={() => setEdit(null)} />}
      {segments && <SegmentsDialog task={segments} onClose={() => setSegments(null)} />}
      {planned && <PlannedEditDialog planned={planned} onClose={() => setPlanned(null)} />}
    </Ctx.Provider>
  );
}

/* ---------- helpers ---------- */

export function useConfirmLongSpan() {
  const { confirm } = useUi();
  return async (start: string, end: string) => {
    const minutes = spanMinutes(start, end);
    if (minutes <= 12 * 60) return true;
    return confirm(`از ${fa(start)} تا ${fa(end)} می‌شود ${fmtDuration(minutes)}. ساعت‌ها درست هستند؟`, "بله، درست است");
  };
}

function describeSpan(start: string, end: string, bad: boolean): { text: string; level: string; minutes?: number } {
  if (bad) return { text: "ساعت نامعتبر است (مثل ۰۹:۳۰)", level: "bad" };
  if (!start || !end) return { text: "", level: "" };
  const minutes = spanMinutes(start, end);
  let text = `مدت: ${fmtDuration(minutes)}`;
  if (end < start) text += " — پایان در روز بعد حساب می‌شود";
  return { text, level: minutes > 12 * 60 ? "warn" : "ok", minutes };
}

export function useDeleteTask() {
  const { confirm } = useUi();
  return async (t: Task) => {
    if (!(await confirm(`تسک «${t.title}» حذف شود؟ این کار قابل برگشت نیست.`))) return false;
    await del(`/api/tasks/${t.id}`);
    await refreshAll();
    return true;
  };
}

/* ---------- task row ---------- */

export function TaskRow({ task: t, reopenable, deletable = true }: { task: Task; reopenable?: boolean; deletable?: boolean }) {
  const { openEdit, openSegments } = useTaskDialogs();
  const deleteTask = useDeleteTask();
  const color = useTagColor();
  const active = t.status === "running" || t.status === "paused";
  const now = useClock();
  const act = (fn: () => Promise<unknown>) => async (e: React.MouseEvent) => { e.stopPropagation(); await fn(); await refreshAll(); };

  const menu = [
    ...(!active && reopenable ? [{ label: "ادامه مجدد ▶", run: async () => { await post(`/api/tasks/${t.id}/reopen`); await refreshAll(); } }] : []),
    { label: "لاگ توقف/ادامه ⏱", run: () => openSegments(t) },
    { label: "ویرایش ✎", run: () => openEdit(t) },
    ...(deletable ? [{ label: "حذف 🗑", danger: true, run: async () => { await deleteTask(t); } }] : []),
  ];

  return (
    <div className={"task-row" + (t.status === "running" ? " running" : "") + (t.status === "paused" ? " paused" : "")} onClick={() => openEdit(t)}>
      <div className="task-main">
        <div className="task-title">
          {t.tag_name && <><span className="task-tag-chip"><i className="tag-dot" style={{ background: color(t.tag_id) }} />{t.tag_name}</span><span className="task-tag-sep"> | </span></>}
          {t.title}
          {active && <span className={"status-chip " + t.status}>{t.status === "running" ? "در حال انجام" : "مکث شده"}</span>}
        </div>
        <div className="task-meta">{fa(t.jalali_date_str)} · {fa(t.start_time || "--")} تا {t.end_time ? fa(t.end_time) : "..."}</div>
      </div>
      {active ? (
        <div className={"task-duration " + (t.status === "running" ? "running-badge" : "paused-badge")}>{fmtDuration(liveMinutes(t, now))}</div>
      ) : null}
      <div className="row-actions">
        {t.status === "running" && <button className="act-btn pause-btn" onClick={act(() => post(`/api/tasks/${t.id}/pause`))}>مکث ⏸</button>}
        {t.status === "paused" && <button className="act-btn resume-btn" onClick={act(() => post(`/api/tasks/${t.id}/resume`))}>ادامه ▶</button>}
        {active && <button className="act-btn stop-btn" onClick={act(() => post(`/api/tasks/${t.id}/stop`))}>پایان ⏹</button>}
        {!active && (
          <div className="task-duration">
            {t.duration_minutes !== null ? <>{fmtDuration(t.duration_minutes)}<span className="duration-minutes-badge">{fa(Math.round(t.duration_minutes))} دقیقه</span></> : "--"}
          </div>
        )}
        <MoreMenu items={menu} />
      </div>
    </div>
  );
}

/* ---------- segments log ---------- */

function SegmentsDialog({ task, onClose }: { task: Task; onClose: () => void }) {
  const [segs, setSegs] = useState<Segment[] | null>(null);
  useEffect(() => { get<Segment[]>(`/api/tasks/${task.id}/segments`).then(setSegs).catch(() => setSegs([])); }, [task.id]);
  const sum = (segs || []).reduce((a, s) => a + s.minutes, 0);
  return (
    <Modal onClose={onClose}>
      <h2>لاگ توقف/ادامه</h2>
      <div className="hint" style={{ marginBottom: 10 }}>{task.title}</div>
      {segs === null && <div className="empty-hint">در حال بارگذاری...</div>}
      {segs && !segs.length && <div className="empty-hint">لاگی برای این تسک ثبت نشده است</div>}
      {segs && task.status === "done" && task.duration_minutes != null && Math.abs(sum - task.duration_minutes) > 1 && (
        <div className="hint" style={{ color: "var(--warning-text)", marginBottom: 8 }}>
          مجموع بازه‌های زیر {fmtDuration(sum)} است ولی مدت ثبت‌شده {fmtDuration(task.duration_minutes)} است؛ احتمالاً ساعت این تسک را دستی ویرایش کرده‌اید. مدت ثبت‌شده معتبر است.
        </div>
      )}
      {segs?.map((s, i) => (
        <div className="segment-row" key={i}>
          <span className="segment-index">{fa(i + 1)}</span>
          <span className="segment-range">از <b>{fa(s.started_label)}</b> تا <b>{s.ongoing ? "در حال انجام" : fa(s.ended_label)}</b></span>
          <span className="segment-minutes">{fmtDuration(s.minutes)}</span>
        </div>
      ))}
      <div className="modal-actions"><div className="spacer" /><button className="btn btn-outline" onClick={onClose}>بستن</button></div>
    </Modal>
  );
}

/* ---------- edit / add task ---------- */

export function GregHint({ date }: { date: YMD }) {
  const [text, setText] = useState("");
  useEffect(() => {
    if (!date.year || !date.month || !date.day) return setText("");
    let alive = true;
    get(`/api/shift-date?year=${date.year}&month=${date.month}&day=${date.day}&delta=0`)
      .then((r) => alive && setText("معادل میلادی: " + gregorianLabel(r.gregorian))).catch(() => alive && setText(""));
    return () => { alive = false; };
  }, [date.year, date.month, date.day]);
  return <div className="greg-hint">{text}</div>;
}

export function EditTaskDialog({ task, preset, onClose }: { task: Task | null; preset?: YMD; onClose: () => void }) {
  const { data: today } = useToday();
  const { confirm } = useUi();
  const confirmLong = useConfirmLongSpan();
  const isLive = !!task && task.status !== "done";
  const initialDate: YMD = task
    ? { year: task.jalali_year, month: task.jalali_month, day: task.jalali_day }
    : preset || { year: today?.jalali_year || 0, month: today?.jalali_month || 1, day: today?.jalali_day || 1 };

  const [title, setTitle] = useState(task?.title || "");
  const [tag, setTag] = useState<number | null>(task?.tag_id ?? null);
  const [date, setDate] = useState<YMD>(initialDate);
  const [start, setStart] = useState(task?.start_time || "");
  const [end, setEnd] = useState(task?.end_time || "");
  const [finish, setFinish] = useState(false);
  const [sign, setSign] = useState("1");
  const [adjH, setAdjH] = useState("");
  const [adjM, setAdjM] = useState("");
  const [bad, setBad] = useState({ start: false, end: false });
  const [error, setError] = useState("");
  const [segs, setSegs] = useState<Segment[]>([]);
  const initial = useRef(JSON.stringify([title, tag, date, start, end]));

  useEffect(() => {
    if (task && task.status === "done") get<Segment[]>(`/api/tasks/${task.id}/segments`).then(setSegs).catch(() => {});
  }, [task?.id]);

  const hasPauses = segs.length > 1;
  const lastStop = [...segs].reverse().find((s) => s.ended_label)?.ended_label || null;
  const adjust = useMemo(() => {
    const h = Number(latin(adjH) || 0), m = Number(latin(adjM) || 0);
    if (!Number.isFinite(h) || !Number.isFinite(m) || h < 0 || m < 0) return NaN;
    return Number(sign) * (h * 60 + m);
  }, [sign, adjH, adjM]);

  const dirty = JSON.stringify([title, tag, date, start, end]) !== initial.current || !!adjH || !!adjM || finish;
  const close = async () => {
    if (dirty && !(await confirm("تغییراتی که ذخیره نکرده‌اید از بین می‌رود. بسته شود؟", "بله، ببند"))) return;
    onClose();
  };

  // live duration line under the time fields
  const info = describeSpan(start, end, bad.start || bad.end);
  const changed = !!task && task.status === "done" && (start !== (task.start_time || "") || end !== (task.end_time || ""));
  const keepsPauses = hasPauses && changed && info.minutes !== undefined && task!.duration_minutes != null;
  if (keepsPauses && task) {
    const origSpan = spanMinutes(task.start_time!, task.end_time!);
    const toLastStop = end === lastStop && start === task.start_time;
    const next = toLastStop ? task.duration_minutes! : Math.max(0, task.duration_minutes! + info.minutes! - origSpan);
    info.text = `مدت جدید: ${fmtDuration(next)} (قبلاً ${fmtDuration(task.duration_minutes)})`;
  }
  if (hasPauses && !changed && task && task.status === "done" && task.duration_minutes != null) {
    info.text = `مدت کار ثبت‌شده: ${fmtDuration(task.duration_minutes)} (مکث‌ها حساب نشده)`;
    info.level = "ok";
  }
  const wrongEnd = hasPauses && lastStop && task?.status === "done" && end !== lastStop;

  let adjustPreview = { text: "", level: "" };
  if (Number.isNaN(adjust)) adjustPreview = { text: "عدد نامعتبر است", level: "bad" };
  else if (task && adjust) {
    const current = task.status === "done" ? task.duration_minutes : task.accumulated_minutes || 0;
    if (current != null) {
      const next = current + adjust;
      adjustPreview = next < 0 ? { text: "با این کاهش، مدت منفی می‌شود", level: "bad" }
        : { text: `مدت جدید: ${fmtDuration(next)} (قبلاً ${fmtDuration(current)})`, level: "ok" };
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (bad.start || bad.end) return setError("ساعت نامعتبر است (فرمت درست مثل ۰۹:۳۰)");
    if (!title.trim()) return setError("لطفاً شرح فعالیت را وارد کنید");
    if (!date.year) return setError("لطفاً سال را وارد کنید");
    if (task && task.status === "done" && !end) return setError("برای تسک تمام‌شده، ساعت پایان را خالی نگذارید");
    if (Number.isNaN(adjust)) return setError("مقدار تعدیل مدت را درست وارد کنید (فقط عدد)");

    const payload: Record<string, unknown> = {
      title: title.trim(), jalali_year: date.year, jalali_month: date.month, jalali_day: date.day, tag_id: tag,
    };
    if (task && adjust) payload.adjust_minutes = adjust;
    if (!task) {
      payload.start_time = start || null;
      payload.end_time = end || null;
    } else {
      // only send times the user actually changed, so a title/tag edit never touches the timer
      if (start && start !== task.start_time) payload.start_time = start;
      if (isLive) {
        if (finish) {
          if (!end) return setError("ساعت پایان را وارد کنید");
          payload.end_time = end;
        }
      } else if (end !== task.end_time) payload.end_time = end;
    }
    if (!(isLive && task)) {
      const effStart = (payload.start_time as string) || task?.start_time || null;
      const effEnd = (payload.end_time as string) || null;
      if (effStart && effEnd && (!task || payload.start_time || payload.end_time) && !(await confirmLong(effStart, effEnd))) return;
    }
    try {
      if (task) await put(`/api/tasks/${task.id}`, payload);
      else await post("/api/tasks", payload);
    } catch (err) { return setError(errorText(err)); }
    onClose();
    await refreshAll();
  }

  async function remove() {
    if (!task || !(await confirm("این تسک حذف شود؟"))) return;
    await del(`/api/tasks/${task.id}`);
    onClose();
    await refreshAll();
  }

  async function onFinish(checked: boolean) {
    setFinish(checked);
    if (!checked) return setEnd("");
    if (!end && task?.status === "paused") {
      try {
        const s = await get<Segment[]>(`/api/tasks/${task.id}/segments`);
        const last = [...s].reverse().find((x) => x.ended_label);
        if (last) setEnd(last.ended_label!);
      } catch { /* leave it empty */ }
    }
  }

  return (
    <Modal onClose={close}>
      <h2>{task ? "ویرایش تسک" : "افزودن تسک برای هر تاریخی"}</h2>
      <form onSubmit={submit}>
        <label className="lbl">شرح فعالیت</label>
        <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <label className="lbl">عنوان استوری</label>
        <TagSelect value={tag} onChange={setTag} />
        <label className="lbl">تاریخ</label>
        <DatePicker value={date} onChange={setDate} />
        <GregHint date={date} />
        <div className="row2">
          <div>
            <label className="lbl">ساعت شروع</label>
            <TimeInput label="ساعت شروع" value={start} onChange={setStart} onInvalid={(b) => setBad((x) => ({ ...x, start: b }))} />
          </div>
          <div>
            <label className="lbl">ساعت پایان</label>
            <TimeInput label="ساعت پایان" value={end} onChange={setEnd} disabled={isLive && !finish} placeholder="۱۰:۳۰" onInvalid={(b) => setBad((x) => ({ ...x, end: b }))} />
          </div>
        </div>
        <div className={"span-preview " + info.level} aria-live="polite">{info.text}</div>
        {wrongEnd && (
          <div className="pause-note">
            آخرین توقف واقعیِ این تسک ساعت <b>{fa(lastStop)}</b> بوده.{" "}
            <button type="button" className="btn btn-outline btn-sm" onClick={() => setEnd(lastStop!)}>پایان را همان بگذار</button>
          </div>
        )}
        {keepsPauses && <div className="pause-note">این تسک چند بار مکث داشته؛ با عوض کردن ساعت‌ها فقط همان مقدارِ تغییر به مدت اضافه یا از آن کم می‌شود و زمان مکث‌ها جزو کار حساب نمی‌شود.</div>}
        {task && (
          <div className="adjust-box">
            <div className="adjust-title">تعدیل مدت <small>(اگر دیر یا زود پایان را زده‌اید)</small></div>
            <div className="adjust-row">
              <select aria-label="اضافه یا کم" value={sign} onChange={(e) => setSign(e.target.value)}>
                <option value="1">+ اضافه کن</option>
                <option value="-1">− کم کن</option>
              </select>
              <input type="text" inputMode="numeric" aria-label="ساعت" placeholder="۰" value={fa(adjH)} onChange={(e) => setAdjH(latin(e.target.value).replace(/\D/g, ""))} /> <span>ساعت</span>
              <input type="text" inputMode="numeric" aria-label="دقیقه" placeholder="۰" value={fa(adjM)} onChange={(e) => setAdjM(latin(e.target.value).replace(/\D/g, ""))} /> <span>دقیقه</span>
            </div>
            <div className={"span-preview " + adjustPreview.level} aria-live="polite">{adjustPreview.text}</div>
          </div>
        )}
        {isLive && (
          <label className="finish-check">
            <input type="checkbox" checked={finish} onChange={(e) => onFinish(e.target.checked)} /> تسک تمام شد (ساعت پایان را خودم وارد می‌کنم)
          </label>
        )}
        <div className="form-error">{error}</div>
        <div className="modal-actions">
          {task && <button type="button" className="btn btn-danger" onClick={remove}>حذف</button>}
          <div className="spacer" />
          <button type="button" className="btn btn-outline" onClick={close}>انصراف</button>
          <button type="submit" className="btn btn-primary">ذخیره</button>
        </div>
      </form>
    </Modal>
  );
}

/* ---------- planned items ---------- */

export async function nextJalaliDay(d: YMD): Promise<YMD> {
  const info = await get(`/api/month-days?year=${d.year}&month=${d.month}`);
  let { year, month, day } = d;
  day += 1;
  if (day > info.days) {
    day = 1;
    month += 1;
    if (month > 12) { month = 1; year += 1; }
  }
  return { year, month, day };
}

export function PlannedRow({ p, after }: { p: Planned; after?: () => void }) {
  const { openPlannedEdit } = useTaskDialogs();
  const { confirm } = useUi();
  const color = useTagColor();
  const reload = async () => { await refreshAll(); after?.(); };
  return (
    <div className={"task-row" + (p.overdue ? " overdue" : "")} style={{ cursor: "default" }}>
      <div className="task-main">
        <div className="task-title">
          {p.tag_name && <><span className="task-tag-chip"><i className="tag-dot" style={{ background: color(p.tag_id) }} />{p.tag_name}</span><span className="task-tag-sep"> | </span></>}
          {p.title}
          {p.overdue && <span className="status-chip overdue-chip">تاریخش گذشته</span>}
        </div>
        <div className="task-meta">{fa(p.jalali_date_str)}</div>
      </div>
      <div className="row-actions">
        <button className="act-btn start-planned-btn" onClick={async () => { await post(`/api/planned/${p.id}/start`); await reload(); }}>شروع ▶</button>
        <MoreMenu items={[
          { label: "انتقال به فردا ▶", run: async () => {
            const n = await nextJalaliDay({ year: p.jalali_year, month: p.jalali_month, day: p.jalali_day });
            await put(`/api/planned/${p.id}`, { jalali_year: n.year, jalali_month: n.month, jalali_day: n.day });
            await reload();
          } },
          { label: "ویرایش ✎", run: () => openPlannedEdit(p) },
          { label: "حذف 🗑", danger: true, run: async () => {
            if (!(await confirm("این تسک برنامه‌ریزی‌شده حذف شود؟"))) return;
            await del(`/api/planned/${p.id}`);
            await reload();
          } },
        ]} />
      </div>
    </div>
  );
}

function PlannedEditDialog({ planned: p, onClose }: { planned: Planned; onClose: () => void }) {
  const { data: today } = useToday();
  const { confirm } = useUi();
  const [title, setTitle] = useState(p.title);
  const [tag, setTag] = useState<number | null>(p.tag_id);
  const [date, setDate] = useState<YMD>({ year: p.jalali_year, month: p.jalali_month, day: p.jalali_day });
  const [error, setError] = useState("");
  const initial = useRef(JSON.stringify([title, tag, date]));
  const close = async () => {
    if (JSON.stringify([title, tag, date]) !== initial.current && !(await confirm("تغییراتی که ذخیره نکرده‌اید از بین می‌رود. بسته شود؟", "بله، ببند"))) return;
    onClose();
  };
  async function save(e: React.FormEvent) {
    e.preventDefault();
    try {
      await put(`/api/planned/${p.id}`, { title: title.trim(), jalali_year: date.year, jalali_month: date.month, jalali_day: date.day, tag_id: tag });
    } catch (err) { return setError(errorText(err)); }
    onClose();
    await refreshAll();
  }
  return (
    <Modal onClose={close}>
      <h2>ویرایش تسک برنامه‌ریزی‌شده</h2>
      <form onSubmit={save}>
        <label className="lbl">شرح فعالیت</label>
        <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <label className="lbl">عنوان استوری</label>
        <TagSelect value={tag} onChange={setTag} />
        <label className="lbl">تاریخ</label>
        <DatePicker value={date} onChange={setDate} />
        <GregHint date={date} />
        <div className="shortcuts">
          <button type="button" className="btn btn-outline" onClick={() => today && setDate({ year: today.jalali_year, month: today.jalali_month, day: today.jalali_day })}>امروز</button>
          <button type="button" className="btn btn-outline" onClick={async () => today && setDate(await nextJalaliDay({ year: today.jalali_year, month: today.jalali_month, day: today.jalali_day }))}>فردا</button>
        </div>
        <div className="form-error">{error}</div>
        <div className="modal-actions">
          <button type="button" className="btn btn-danger" onClick={async () => {
            if (!(await confirm("این تسک برنامه‌ریزی‌شده حذف شود؟"))) return;
            await del(`/api/planned/${p.id}`);
            onClose();
            await refreshAll();
          }}>حذف</button>
          <div className="spacer" />
          <button type="button" className="btn btn-outline" onClick={close}>انصراف</button>
          <button type="submit" className="btn btn-primary">ذخیره</button>
        </div>
      </form>
    </Modal>
  );
}

/* ---------- the "now" clock text helpers used by several pages ---------- */

export function useServerClock() {
  const now = useClock();
  const d = serverNow(now);
  return d;
}
