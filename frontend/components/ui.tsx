"use client";
import { createContext, ReactNode, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import { fa, latin, MONTHS, parseTimeText } from "@/lib/fa";
import { serverClock } from "@/lib/data";
import { get } from "@/lib/api";
import { Tag } from "@/lib/types";

/* ---------------- toast + confirm ---------------- */

interface UiCtx {
  toast: (message: string) => void;
  confirm: (message: string, yesLabel?: string) => Promise<boolean>;
}
const Ctx = createContext<UiCtx>({ toast: () => {}, confirm: async () => false });
export const useUi = () => useContext(Ctx);

export function UiProvider({ children }: { children: ReactNode }) {
  const [toastText, setToastText] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [ask, setAsk] = useState<{ message: string; yes?: string; resolve: (v: boolean) => void } | null>(null);

  const toast = useCallback((message: string) => {
    setToastText(message);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToastText(""), 4500);
  }, []);
  const confirm = useCallback(
    (message: string, yes?: string) => new Promise<boolean>((resolve) => setAsk({ message, yes, resolve })),
    [],
  );
  const answer = (v: boolean) => {
    ask?.resolve(v);
    setAsk(null);
  };

  useEffect(() => {
    const onRejection = (e: PromiseRejectionEvent) => toast(`خطا: ${(e.reason && e.reason.message) || "عملیات انجام نشد"}`);
    window.addEventListener("unhandledrejection", onRejection);
    return () => window.removeEventListener("unhandledrejection", onRejection);
  }, [toast]);

  return (
    <Ctx.Provider value={{ toast, confirm }}>
      {children}
      {ask && (
        <Modal onClose={() => answer(false)} className="confirm-modal">
          <p>{ask.message}</p>
          <div className="modal-actions">
            <div className="spacer" />
            <button className="btn btn-outline" onClick={() => answer(false)}>انصراف</button>
            <button className={"btn " + (ask.yes ? "btn-primary" : "btn-danger")} onClick={() => answer(true)}>{ask.yes || "بله، حذف کن"}</button>
          </div>
        </Modal>
      )}
      {toastText && <div className="toast" role="alert">{toastText}</div>}
    </Ctx.Provider>
  );
}

/* ---------------- modal ---------------- */

export function Modal({ children, onClose, className = "" }: { children: ReactNode; onClose: () => void; className?: string }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={"modal " + className} role="dialog" aria-modal="true">{children}</div>
    </div>
  );
}

/* ---------------- row menu (three dots) ---------------- */

export interface MenuItem {
  label: string;
  danger?: boolean;
  run: () => void | Promise<void>;
}

export function MoreMenu({ items }: { items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ left: 8, top: 8 });
  const btn = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !btn.current || !menu.current) return;
    const r = btn.current.getBoundingClientRect();
    const w = menu.current.offsetWidth, h = menu.current.offsetHeight;
    const left = Math.min(Math.max(8, r.left), window.innerWidth - w - 8);
    let top = r.bottom + 4;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 4);
    setPos({ left, top });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e.type === "mousedown" && menu.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", close, true);
    return () => {
      document.removeEventListener("mousedown", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <>
      <button ref={btn} type="button" className="more-btn" aria-label="گزینه‌های بیشتر" aria-haspopup="menu" aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>
        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><circle cx="12" cy="5" r="2.2" /><circle cx="12" cy="12" r="2.2" /><circle cx="12" cy="19" r="2.2" /></svg>
      </button>
      {open && (
        <div ref={menu} className="row-menu" role="menu" style={{ left: pos.left, top: pos.top }} onClick={(e) => e.stopPropagation()}>
          {items.map((it) => (
            <button key={it.label} type="button" role="menuitem" className={"row-menu-item" + (it.danger ? " danger" : "")}
              onClick={async () => { setOpen(false); await it.run(); }}>{it.label}</button>
          ))}
        </div>
      )}
    </>
  );
}

/* ---------------- inputs ---------------- */

/** HH:MM field with Persian digits, automatic colon and an "اکنون" button. `value` is "HH:MM" or "". */
export function TimeInput({ value, onChange, disabled, placeholder = "۰۹:۳۰", label, onInvalid }: {
  value: string; onChange: (v: string) => void; disabled?: boolean; placeholder?: string; label: string;
  onInvalid?: (bad: boolean) => void;
}) {
  const [text, setText] = useState(fa(value));
  const [bad, setBad] = useState(false);
  const last = useRef(value);

  useEffect(() => {
    // external change (reset, "set end to last stop", ...)
    if (value !== last.current) {
      last.current = value;
      setText(fa(value));
      setBad(false);
    }
  }, [value]);

  const apply = (raw: string) => {
    const digits = latin(raw).replace(/\D/g, "").slice(0, 4);
    const shown = digits.length > 2 ? `${digits.slice(0, digits.length - 2)}:${digits.slice(-2)}` : digits;
    setText(fa(shown));
    const parsed = parseTimeText(shown);
    setBad(parsed.state === "bad");
    onInvalid?.(parsed.state === "bad");
    last.current = parsed.value;
    onChange(parsed.value);
  };

  return (
    <div className="time-field">
      <input type="text" inputMode="numeric" dir="ltr" autoComplete="off" maxLength={5} aria-label={label} placeholder={disabled ? "" : placeholder}
        className={bad ? "invalid" : ""} value={text} disabled={disabled} onChange={(e) => apply(e.target.value)}
        onBlur={() => { const p = parseTimeText(text); if (p.state === "ok") setText(fa(p.value)); }} />
      <button type="button" className="time-now-btn" tabIndex={-1} disabled={disabled} onClick={() => apply(serverClock())}>اکنون</button>
    </div>
  );
}

/** Numeric text field shown with Persian digits; `value` is a plain-digit string. */
export function NumInput({ value, onChange, label, maxLength, placeholder, className }: {
  value: string; onChange: (v: string) => void; label: string; maxLength?: number; placeholder?: string; className?: string;
}) {
  return (
    <input type="text" inputMode="numeric" aria-label={label} maxLength={maxLength} placeholder={placeholder} className={className}
      value={fa(value)} onChange={(e) => onChange(latin(e.target.value).replace(/\D/g, ""))} />
  );
}

export interface YMD { year: number; month: number; day: number }

/** Jalali year / month / day pickers; the day list follows the month length (the server knows leap years). */
export function DatePicker({ value, onChange }: { value: YMD; onChange: (v: YMD) => void }) {
  const [esfandDays, setEsfandDays] = useState(29);
  useEffect(() => {
    if (value.month !== 12 || !value.year) return;
    let alive = true;
    get(`/api/month-days?year=${value.year}&month=12`).then((r) => alive && setEsfandDays(r.days)).catch(() => {});
    return () => { alive = false; };
  }, [value.year, value.month]);
  const count = value.month <= 6 ? 31 : value.month <= 11 ? 30 : esfandDays;
  const day = Math.min(Math.max(value.day, 1), count);

  return (
    <div className="row3">
      <div>
        <label className="lbl">سال</label>
        <NumInput label="سال" maxLength={4} value={String(value.year || "")} onChange={(v) => onChange({ ...value, year: Number(v) || 0 })} />
      </div>
      <div>
        <label className="lbl">ماه</label>
        <select aria-label="ماه" value={value.month} onChange={(e) => onChange({ ...value, month: Number(e.target.value) })}>
          {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </select>
      </div>
      <div>
        <label className="lbl">روز</label>
        <select aria-label="روز" value={day} onChange={(e) => onChange({ ...value, day: Number(e.target.value) })}>
          {Array.from({ length: count }, (_, i) => <option key={i} value={i + 1}>{fa(i + 1)}</option>)}
        </select>
      </div>
    </div>
  );
}

/* ---------------- budget bar ---------------- */

export function budgetLevel(pct: number) { return pct > 100 ? "over" : pct >= 80 ? "warn" : "ok"; }

export function BudgetBar({ percent }: { percent: number | null }) {
  const pct = percent || 0;
  return <div className="budget-bar"><span className={"budget-fill " + budgetLevel(pct)} style={{ width: Math.min(100, pct) + "%" }} /></div>;
}

export function budgetText(tag: Pick<Tag, "budget_minutes" | "spent_minutes" | "budget_percent">, hm: (m: number) => string): string {
  const pct = tag.budget_percent || 0;
  const left = (tag.budget_minutes || 0) - (tag.spent_minutes || 0);
  const tail = left >= 0 ? `${hm(left)} مانده` : `${hm(-left)} بیشتر از تخمین`;
  return `${hm(tag.spent_minutes || 0)} از ${hm(tag.budget_minutes || 0)} · ${fa(Math.round(pct))}٪ · ${tail}`;
}
