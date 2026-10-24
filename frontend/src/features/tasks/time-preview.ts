import { fmtDuration, spanMinutes } from "@/lib/format";

/** Live "مدت" line under start/end fields, so a wrong time is visible before saving. */
export function describe(start: string, end: string, bad: boolean): { text: string; level: string; minutes?: number } {
  if (bad) return { text: "ساعت نامعتبر است (مثل ۰۹:۳۰)", level: "bad" };
  if (!start || !end) return { text: "", level: "" };
  const minutes = spanMinutes(start, end);
  let text = `مدت: ${fmtDuration(minutes)}`;
  if (end < start) text += " — پایان در روز بعد حساب می‌شود";
  return { text, level: minutes > 12 * 60 ? "warn" : "ok", minutes };
}
