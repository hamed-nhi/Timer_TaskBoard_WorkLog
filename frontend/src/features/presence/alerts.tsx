"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { refreshAll } from "@/lib/data";
import { fa, fmtDuration } from "@/lib/format";
import { PresenceSegment } from "@/lib/types";
import { setDaylogDay } from "@/features/daylog/navigation";
import { SegmentDialog } from "@/features/presence/components";
import { Modal } from "@/shared/ui";

type Alert = { date: string; jalali: string; year: number; month: number; day: number; task_minutes: number; fill_minutes: number; reported_minutes: number; presence_minutes: number; excess_minutes: number; unclosed: boolean; segments: { id: number; start: string; end: string | null }[] };

export function PresenceAlerts({ date }: { date?: string }) {
  const router = useRouter();
  const { data, error } = useSWR<{ days: Alert[]; count: number }>(`/api/presence/alerts${date ? `?date=${date}` : ""}`, fetcher, { refreshInterval: 60_000, keepPreviousData: false });
  const [expanded, setExpanded] = useState(false);
  const [selected, setSelected] = useState<Alert | null>(null);
  const [edit, setEdit] = useState<{ day: Alert; segment: PresenceSegment | null } | null>(null);
  if (error) return <div className="presence-alerts check-error" role="status">بررسی تطابق تسک‌ها و حضور انجام نشد؛ اتصال را بررسی کنید.</div>;
  if (!data?.days.length) return null;
  const open = (day: Alert, segment: Alert["segments"][number] | null) => {
    setSelected(null);
    setEdit({ day, segment: segment ? { ...segment, minutes: 0, open: !segment.end, kind: null, note: null } as PresenceSegment : null });
  };
  return <>
    <section className="presence-alerts" aria-label="هشدار مغایرت حضور" role="status">
      <div className="alert-heading"><span className="alert-symbol" aria-hidden="true">!</span><div><strong>زمان تسک‌ها بیشتر از حضور ثبت شده است</strong><p>این هشدار فقط برای روزهای گذشته است؛ حضور یا زمان تسک‌ها را بررسی کنید.</p></div></div>
      {(expanded ? data.days : data.days.slice(0, 1)).map((day) => <div className="presence-alert-row" key={day.date}><div><b>{fa(day.jalali)}</b><span>حدود {fmtDuration(Math.ceil(day.excess_minutes))} بیشتر از حضور</span><small>تسک و تکمیلی: {fmtDuration(day.reported_minutes)} · حضور: {fmtDuration(day.presence_minutes)}{day.unclosed ? " · خروج ثبت نشده" : ""}</small></div><div className="alert-actions"><button className="btn btn-outline btn-sm" onClick={() => day.segments.length ? setSelected(day) : open(day, null)}>اصلاح حضور</button>{!date && <button className="btn btn-link" onClick={() => { setDaylogDay({ year: day.year, month: day.month, day: day.day, gregorian: day.date }); router.push("/daylog/"); }}>مشاهده تسک‌ها</button>}</div></div>)}
      {data.days.length > 1 && <button className="btn btn-link" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "نمایش کمتر" : `نمایش ${fa(data.days.length - 1)} روز دیگر`}</button>}
      {data.count > data.days.length && <div className="hint">آخرین {fa(data.days.length)} روز از {fa(data.count)} روز نمایش داده می‌شود؛ روزهای قدیمی‌تر در گزارش روزانه قابل بررسی‌اند.</div>}
    </section>
    {selected && <Modal onClose={() => setSelected(null)}><h2>اصلاح حضور {fa(selected.jalali)}</h2><p className="hint">بازه‌های واقعی حضور را بررسی کنید. زمان تسک‌ها خودکار تغییر نمی‌کند.</p>{selected.segments.map((segment) => <div className="presence-seg" key={segment.id}><span>{fa(segment.start)} تا {segment.end ? fa(segment.end) : "خروج ثبت نشده"}</span><button className="btn btn-outline btn-sm" onClick={() => open(selected, segment)}>ویرایش</button></div>)}<div className="modal-actions"><button className="btn btn-primary" onClick={() => open(selected, null)}>افزودن بازه حضور</button><button className="btn btn-outline" onClick={() => setSelected(null)}>بستن</button></div></Modal>}
    {edit && <SegmentDialog seg={edit.segment} date={edit.day.date} onClose={() => setEdit(null)} onSaved={async () => { await refreshAll(); }} />}
  </>;
}
