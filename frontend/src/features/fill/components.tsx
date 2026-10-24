"use client";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { errorText, get, post } from "@/lib/api";
import { fa, fmtDuration, gregorianLabel } from "@/lib/format";
import { refreshAll, useToday } from "@/lib/data";
import { FillSuggestion } from "@/lib/types";
import { Modal, useUi } from "@/shared/ui";

interface FillCtx {
  openFill: (gdate: string) => void;
  rollback: (gdate: string) => Promise<void>;
}
const Ctx = createContext<FillCtx>({ openFill: () => {}, rollback: async () => {} });
export const useFill = () => useContext(Ctx);

export function FillProvider({ children }: { children: ReactNode }) {
  const [date, setDate] = useState<string | null>(null);
  const { confirm, toast } = useUi();

  async function rollback(gdate: string) {
    if (!(await confirm("تکمیلی این روز حذف شود و گزارش به همان زمان ثبت‌شده‌ی تسک‌ها برگردد؟", "بله، برگردان"))) return;
    const r = await post("/api/fill/rollback", { date: gdate });
    toast(`${fa(Math.round(r.removed_minutes))} دقیقه تکمیلی برداشته شد`);
    await refreshAll();
  }

  return (
    <Ctx.Provider value={{ openFill: setDate, rollback }}>
      {children}
      {date && <FillDialog date={date} onClose={() => setDate(null)} />}
    </Ctx.Provider>
  );
}

/** Report-hours fill: suggest report-only minutes, let the user edit them, preview, then confirm. */
function FillDialog({ date, onClose }: { date: string; onClose: () => void }) {
  const { data: today } = useToday();
  const { toast } = useUi();
  const [fill, setFill] = useState<FillSuggestion | null>(null);
  const [values, setValues] = useState<Record<number, number>>({});
  const [step, setStep] = useState<"ask" | "preview">("ask");
  const [manual, setManual] = useState(false);
  const [percent, setPercent] = useState("");
  const [error, setError] = useState("");

  async function load(pct?: string) {
    setError("");
    try {
      // always a fresh suggestion, never the values saved earlier
      const s = await get<FillSuggestion>(`/api/fill-suggestion?date=${date}${pct ? `&percent=${encodeURIComponent(pct)}` : ""}`);
      setFill(s);
      setValues(Object.fromEntries(s.items.map((i) => [i.id, i.suggested])));
      setPercent(String(Math.round(s.percent)));
    } catch (e) { setError(errorText(e)); }
  }
  useEffect(() => { load(); }, [date]);

  const total = Object.values(values).reduce((a, b) => a + b, 0);
  const over = !!fill && total > fill.allowed_minutes + 1;

  async function save() {
    if (!fill) return;
    try {
      await post("/api/fill", { date: fill.date, items: fill.items.map((i) => ({ id: i.id, fill_minutes: values[i.id] || 0 })), percent: Number(percent) || null });
    } catch (e) { return setError(errorText(e)); }
    onClose();
    toast("ساعت گزارش ثبت شد (زمان واقعی تسک‌ها دست نخورد)");
    await refreshAll();
  }

  function sentence() {
    if (!fill) return <span>در حال محاسبه...</span>;
    if (fill.blocked && !total) {
      return <>پیشنهادی داده نمی‌شود و تسک‌ها با زمان ثبت‌شده‌ی خودشان گزارش می‌شوند. اگر لازم است با «تغییر دستی» خودتان عدد بدهید.</>;
    }
    if (!fill.presence_minutes) return <>برای این روز حضوری ثبت نشده؛ اگر می‌خواهید، با «تغییر دستی» دقیقه‌ها را خودتان وارد کنید.</>;
    const isToday = fill.date === today?.gregorian;
    const head = <>{isToday ? "امروز" : "این روز"} <b>{fmtDuration(fill.presence_minutes)}</b> در شرکت بودید و <b>{fmtDuration(fill.task_minutes)}</b> تسک ثبت کرده‌اید.</>;
    const parts = fill.items.filter((i) => values[i.id] > 0);
    if (!parts.length) {
      return <>{head}<br />{fill.needed_minutes > 0
        ? "چیزی برای اضافه کردن پیشنهاد نشد (فقط جلسه یا تسک‌های با وزن ۰ دارید)؛ با «تغییر دستی» خودتان وارد کنید."
        : "تسک‌هایتان به هدف رسیده؛ نیازی به تکمیل نیست."}</>;
    }
    const report = fill.task_minutes + total;
    const pct = Math.round((report / fill.presence_minutes) * 100);
    return (
      <>
        {head}<br />پیشنهاد:{" "}
        {parts.map((i, k) => <span key={i.id}>{k > 0 && "، "}<b>{fa(values[i.id])} دقیقه</b> به «{i.title}»</span>)}
        {" "}اضافه شود تا گزارش به <b>{fmtDuration(report)}</b> ({fa(pct)}٪ حضور) برسد.
        {fill.current_fill_total > 0 && <><br /><span className="hint">قبلاً {fa(Math.round(fill.current_fill_total))} دقیقه تکمیلی ثبت شده بود؛ با تأیید، این پیشنهاد جای آن را می‌گیرد.</span></>}
        {over && <div className="form-error">بیشتر از سقف است: حداکثر {fa(Math.floor(fill.allowed_minutes))} دقیقه ({fa(Math.round(fill.percent))}٪ حضور).</div>}
      </>
    );
  }

  return (
    <Modal onClose={onClose} className="modal-xwide">
      <h2>تکمیل ساعت گزارش <span className="fill-date">{fill ? gregorianLabel(fill.date) : ""}</span></h2>
      {fill && step === "ask" && (
        <div>
          {fill.warnings.length > 0 && <div className="presence-note">{fill.warnings.map((w, i) => <div key={i}>{w}</div>)}</div>}
          <div className="fill-sentence">{sentence()}</div>
          {manual && (
            <div className="fill-manual">
              {fill.items.map((i) => (
                <label className="fill-manual-row" key={i.id}>
                  <span>{i.title} ({fa(Math.round(i.minutes))} دقیقه)</span>
                  <input type="number" min={0} max={600} step={5} inputMode="numeric" value={values[i.id] ?? 0}
                    onChange={(e) => setValues({ ...values, [i.id]: Math.max(0, Math.round(Number(e.target.value) || 0)) })} />
                  <span>+ دقیقه</span>
                </label>
              ))}
            </div>
          )}
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={() => setManual(!manual)}>تغییر دستی</button>
            <div className="spacer" />
            <button className="btn btn-outline" onClick={onClose}>انصراف</button>
            <button className="btn btn-primary" disabled={over} onClick={() => setStep("preview")}>ادامه و پیش‌نمایش ←</button>
          </div>
        </div>
      )}
      {fill && step === "preview" && (
        <div>
          <div className="fill-sentence">گزارش نهایی این روز این‌طور می‌شود؛ اگر درست است تأیید کنید:</div>
          <div className="table-scroll">
            <table className="daylog-table">
              <thead><tr><th>تسک</th><th>زمان واقعی</th><th>اضافه</th><th>در گزارش</th></tr></thead>
              <tbody>
                {fill.items.map((i) => {
                  const add = values[i.id] || 0;
                  return (
                    <tr key={i.id} className={add ? "fill-changed" : ""}>
                      <td>{i.title}</td><td>{fa(Math.round(i.minutes))}</td><td>{add ? "+" + fa(add) : "—"}</td><td><b>{fa(Math.round(i.minutes + add))}</b></td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td>جمع</td><td>{fmtDuration(fill.task_minutes)}</td><td>+{fa(total)}</td>
                  <td><b>{fmtDuration(fill.task_minutes + total)}</b>{fill.presence_minutes ? ` · ${fa(Math.round(((fill.task_minutes + total) / fill.presence_minutes) * 100))}٪ حضور` : ""}</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <div className="modal-actions">
            <button className="btn btn-outline" onClick={() => setStep("ask")}>→ برگرد و تغییر بده</button>
            <div className="spacer" />
            <button className="btn btn-primary" onClick={save}>تأیید نهایی و ثبت</button>
          </div>
        </div>
      )}
      <details className="fill-settings">
        <summary>{fill ? `هدف: ${fa(Math.round(fill.percent))}٪ حضور (تغییر)` : "هدف"}</summary>
        <label>تسک‌ها به <input type="number" min={50} max={95} step={1} inputMode="numeric" value={percent} onChange={(e) => setPercent(e.target.value)} /> درصد حضور برسند</label>
        <button className="btn btn-outline btn-sm" onClick={() => { setStep("ask"); load(percent); }}>محاسبه‌ی دوباره</button>
      </details>
      <div className="hint" style={{ marginTop: 10 }}>زمان واقعی تسک‌ها دست نمی‌خورد؛ این دقیقه‌ها فقط در گزارش برای سامانه جمع می‌شوند.</div>
      <div className="form-error">{error}</div>
    </Modal>
  );
}
