"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { del, errorText, fetcher, post, put } from "@/lib/api";
import { fa, fmtDuration } from "@/lib/fa";
import { refreshAll, useClock, usePresence, useToday } from "@/lib/data";
import { Presence, PresenceSegment } from "@/lib/types";
import { Modal, TimeInput, useUi } from "./ui";
import { useFill } from "./fill";

const LEAVE_REASONS = ["ناهار", "نماز / استراحت", "کار بیرون از شرکت", "کار شخصی"];

/** Presence data plus the moment it was fetched, so totals can tick between refreshes. */
export function useLivePresence() {
  const { data, mutate } = usePresence();
  const now = useClock();
  const at = useRef(Date.now());
  useEffect(() => { at.current = Date.now(); }, [data]);
  const elapsed = Math.max(0, (now - at.current) / 60000);
  const live = data && {
    total: data.total_minutes + (data.status === "in" ? elapsed : 0),
    tasks: data.task_minutes + (data.running_task ? elapsed : 0),
  };
  return { presence: data, live, mutate };
}

function taskLabel(p: Presence) {
  if (p.running_task) return `تسک در حال اجرا: «${p.running_task}»`;
  if (p.paused_task) return `تسک «${p.paused_task}» در حالت مکث`;
  return "تسکی در حال اجرا نیست";
}

/** Small status chip in the top bar. */
export function PresenceChip() {
  const { presence: p } = useLivePresence();
  if (!p) return null;
  const last = p.segments[p.segments.length - 1];
  const line = p.status === "in" ? "حضور: در شرکت ●" : p.status === "break" ? "حضور: مکث (ناهار / استراحت)"
    : p.status === "done" ? `حضور: پایان کار ${fa(last?.end)}` : "حضور: ثبت نشده";
  return (
    <Link href="/" className={"presence-chip " + p.status} title="حضور در شرکت؛ برای رفتن به کارت حضور کلیک کنید">
      <span className="pc-line">{line}</span>
      <span className="pc-line pc-task">{taskLabel(p)}</span>
    </Link>
  );
}

export function PresenceCard() {
  const { presence: p, live, mutate } = useLivePresence();
  const { confirm, toast } = useUi();
  const { openFill, rollback } = useFill();
  const { data: today } = useToday();
  const [leaveOpen, setLeaveOpen] = useState(false);
  const [edit, setEdit] = useState<PresenceSegment | "new" | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  if (!p || !live) return <div className="card presence-card"><div className="empty-hint">...</div></div>;
  const last = p.segments[p.segments.length - 1];
  const gap = Math.max(0, live.total - live.tasks);

  async function action(fn: () => Promise<Presence>) {
    try { await mutate(await fn(), { revalidate: false }); await refreshAll(); } catch (e) { toast(errorText(e)); }
  }

  // leaving while a task still runs: offer to pause it too, otherwise it keeps counting
  async function pauseRunningFirst() {
    if (!p?.running_task_id) return true;
    if (!(await confirm(`تسک «${p.running_task}» هنوز در حال اجراست؛ همراه خروج مکث شود؟`, "بله، مکث کن و برو"))) return false;
    try { await post(`/api/tasks/${p.running_task_id}/pause`); } catch (e) { toast(errorText(e)); return false; }
    return true;
  }

  async function toggle() {
    if (p!.status !== "in") return action(() => post("/api/presence/start"));
    if (await pauseRunningFirst()) setLeaveOpen(true);
  }

  async function leave(reason: string) {
    setLeaveOpen(false);
    await action(() => post("/api/presence/pause", { note: reason }));
  }

  async function finish() {
    if (!(await confirm("پایان کار و خروج کامل از شرکت ثبت شود؟", "بله، پایان کار"))) return;
    if (!(await pauseRunningFirst())) return;
    await action(() => post("/api/presence/finish"));
  }

  const status = p.status === "in" ? `در شرکت هستید؛ از ساعت ${fa(last.start)}`
    : p.status === "break" ? `بیرون از شرکت (ناهار / استراحت)؛ از ساعت ${fa(last.end)}`
    : p.status === "done" ? `کار امروز تمام شد؛ خروج ساعت ${fa(last.end)}` : "امروز هنوز ورودی ثبت نشده";
  const btnLabel = p.status === "in" ? "خروج برای ناهار / استراحت" : p.status === "break" ? "بازگشت به شرکت" : p.status === "done" ? "ورود دوباره" : "ورود";
  const btnClass = p.status === "in" || p.status === "done" ? "btn btn-outline" : "btn btn-primary";
  const first = p.segments[0];
  const early = first && p.first_task_start && p.first_task_start < first.start;
  const breakMinutes = p.status === "break" && last?.end ? (() => {
    const [h, m] = last.end.split(":").map(Number);
    const n = new Date();
    return n.getHours() * 60 + n.getMinutes() - (h * 60 + m);
  })() : 0;

  return (
    <div className="card presence-card" id="presenceCard">
      <div className="presence-head">
        <div>
          <div className="presence-title">حضور در شرکت</div>
          <div className="presence-status">{status}</div>
        </div>
        <div className="presence-btns">
          <button className={btnClass} onClick={toggle}>{btnLabel}</button>
          {(p.status === "in" || p.status === "break") && <button className="btn btn-danger" onClick={finish}>پایان کار (خروج کامل)</button>}
        </div>
      </div>

      {p.needs_checkin && (
        <div className="presence-note reminder">
          <span>یادآوری: تسک «{p.running_task}» در حال اجراست ولی ورود شما به شرکت ثبت نشده.</span>
          <button className="btn btn-primary btn-sm" onClick={() => action(() => post("/api/presence/start"))}>ثبت ورود (همین الان)</button>
          {p.status === "none" && p.first_task_start && (
            <button className="btn btn-outline btn-sm" onClick={() => action(() => post("/api/presence", { start_time: p.first_task_start }))}>
              ورود را ساعت {fa(p.first_task_start)} (اولین تسک) بگذار
            </button>
          )}
        </div>
      )}
      {!p.needs_checkin && early && (
        <div className="presence-note">
          اولین تسک امروز ساعت {fa(p.first_task_start)} شروع شده، ولی ورود شما {fa(first.start)} ثبت است.{" "}
          <button className="btn btn-outline btn-sm" onClick={() => action(() => put(`/api/presence/${first.id}`, { start_time: p.first_task_start, end_time: first.end }))}>
            ساعت ورود را {fa(p.first_task_start)} بگذار
          </button>
        </div>
      )}
      {breakMinutes > 240 && <div className="presence-note">بیش از ۴ ساعت است که بیرون از شرکت ثبت شده‌اید؛ اگر برگشته‌اید «بازگشت به شرکت» را بزنید یا ساعت‌ها را ویرایش کنید.</div>}

      <div className="presence-stats">
        <div><span className="ps-label">مدت حضور امروز</span><b>{fmtDuration(live.total)}</b></div>
        <div><span className="ps-label">مجموع تسک‌ها</span><b>{fmtDuration(live.tasks)}</b></div>
        <div><span className="ps-label">حضور بدون تسک</span><b>{fmtDuration(gap)}</b></div>
        {p.fill_minutes > 0 && (
          <div className="report-box">
            <span className="ps-label">تسک + تکمیلی (گزارش)</span><b>{fmtDuration(live.tasks + p.fill_minutes)}</b>
            <button className="btn btn-outline fill-rollback-btn" onClick={() => today && rollback(today.gregorian)}>↶ برگرداندن به زمان ثبت‌شده</button>
          </div>
        )}
      </div>

      <div className="presence-list">
        {p.segments.map((s) => (
          <div className="presence-seg" key={s.id}>
            <span>
              {fa(s.start)} تا {s.end ? fa(s.end) : "الان"} ({fmtDuration(s.minutes)})
              {s.kind === "end" ? "  ← پایان کار" : s.note ? `  ← خروج: ${s.note}` : s.end ? "  ← خروج موقت" : ""}
            </span>
            <button className="btn btn-outline btn-sm" onClick={() => setEdit(s)}>ویرایش</button>
          </div>
        ))}
      </div>
      <div className="presence-foot">
        <button className="btn btn-outline btn-sm" onClick={() => setEdit("new")}>+ افزودن بازه‌ی حضور</button>
        <button className="btn btn-outline btn-sm" onClick={() => today && openFill(today.gregorian)}>تکمیل ساعت گزارش</button>
      </div>
      <details className="how-to" onToggle={(e) => setShowHistory((e.target as HTMLDetailsElement).open)}>
        <summary>حضور روزهای قبل</summary>
        {showHistory && <History today={today?.gregorian} />}
      </details>
      <div className="hint">ورود و خروج فقط با دکمه‌های خودتان ثبت می‌شود (در نسخه‌ی وب ورود خودکار وجود ندارد). «خروج برای ناهار» و «بازگشت» ساعت‌ها را ثبت می‌کنند؛ «پایان کار» خروج کامل است. مدت حضور جدا از تسک‌هاست و به آن‌ها دست نمی‌زند.</div>

      {leaveOpen && <LeaveDialog onPick={leave} onClose={() => setLeaveOpen(false)} />}
      {edit && <SegmentDialog seg={edit === "new" ? null : edit} onClose={() => setEdit(null)} onSaved={async (np) => { await mutate(np, { revalidate: false }); await refreshAll(); }} />}
    </div>
  );
}

function History({ today }: { today?: string }) {
  const { data } = useSWR<any[]>("/api/presence/history", fetcher);
  const days = (data || []).filter((d) => d.date !== today);
  if (!data) return <div className="empty-hint">...</div>;
  if (!days.length) return <div className="empty-hint">هنوز روز قبلی ثبت نشده؛ از امروز جمع می‌شود</div>;
  return (
    <div className="presence-list">
      {days.map((d) => (
        <div className="presence-seg" key={d.date} style={{ flexWrap: "wrap" }}>
          {fa(d.jalali)} | {fa(d.first)} تا {d.last ? fa(d.last) : "بدون خروج"} | حضور {fmtDuration(d.presence_minutes)} | تسک {fmtDuration(d.task_minutes)} | بدون تسک {fmtDuration(d.gap_minutes)}
          {d.unclosed ? " (خروج ثبت نشده)" : ""}
        </div>
      ))}
    </div>
  );
}

function LeaveDialog({ onPick, onClose }: { onPick: (reason: string) => void; onClose: () => void }) {
  const [other, setOther] = useState("");
  return (
    <Modal onClose={onClose}>
      <h2>خروج موقت از شرکت</h2>
      <div className="hint">دلیل بیرون رفتن را انتخاب کنید (می‌تواند چند ساعت هم طول بکشد):</div>
      <div className="leave-reasons">
        {LEAVE_REASONS.map((r) => <button key={r} className="btn btn-outline" onClick={() => onPick(r)}>{r}</button>)}
      </div>
      <input type="text" maxLength={60} placeholder="یا دلیل دیگر را بنویسید (اختیاری)" value={other} onChange={(e) => setOther(e.target.value)} />
      <div className="modal-actions">
        <div className="spacer" />
        <button className="btn btn-outline" onClick={onClose}>انصراف</button>
        <button className="btn btn-primary" onClick={() => onPick(other.trim())}>ثبت خروج</button>
      </div>
    </Modal>
  );
}

function SegmentDialog({ seg, onClose, onSaved }: { seg: PresenceSegment | null; onClose: () => void; onSaved: (p: Presence) => Promise<void> }) {
  const { confirm } = useUi();
  const [start, setStart] = useState(seg?.start || "");
  const [end, setEnd] = useState(seg?.end || "");
  const [error, setError] = useState("");
  const [bad, setBad] = useState(false);

  async function save() {
    if (bad) return setError("ساعت نامعتبر است (فرمت درست مثل ۰۹:۳۰)");
    if (!start) return setError("ساعت ورود را وارد کنید");
    try {
      const p = seg ? await put(`/api/presence/${seg.id}`, { start_time: start, end_time: end || null })
        : await post("/api/presence", { start_time: start, end_time: end || null });
      await onSaved(p);
      onClose();
    } catch (e) { setError(errorText(e)); }
  }
  async function remove() {
    if (!seg) return;
    onClose();
    if (!(await confirm("این بازه‌ی حضور حذف شود؟ (به تسک‌ها دست نمی‌زند)"))) return;
    await onSaved(await del(`/api/presence/${seg.id}`));
  }
  return (
    <Modal onClose={onClose}>
      <h2>{seg ? "ویرایش بازه‌ی حضور" : "افزودن بازه‌ی حضور"}</h2>
      <div className="row2">
        <div><label className="lbl">ساعت ورود</label><TimeInput label="ساعت ورود" value={start} onChange={setStart} placeholder="۰۸:۰۰" onInvalid={setBad} /></div>
        <div><label className="lbl">ساعت خروج (خالی = هنوز در شرکت)</label><TimeInput label="ساعت خروج" value={end} onChange={setEnd} placeholder="۱۲:۳۰" onInvalid={setBad} /></div>
      </div>
      <div className="form-error">{error}</div>
      <div className="modal-actions">
        {seg && <button className="btn btn-danger" onClick={remove}>حذف</button>}
        <div className="spacer" />
        <button className="btn btn-outline" onClick={onClose}>انصراف</button>
        <button className="btn btn-primary" onClick={save}>ذخیره</button>
      </div>
    </Modal>
  );
}
