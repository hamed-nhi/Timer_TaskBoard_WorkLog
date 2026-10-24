// Persian presentation helpers: digits, durations, month and weekday names.

export const MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];
export const WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]; // Saturday first
export const WEEKDAYS_SHORT = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
export const GREGORIAN_MONTHS = ["ژانویه", "فوریه", "مارس", "آوریل", "مه", "ژوئن", "ژوئیه", "اوت", "سپتامبر", "اکتبر", "نوامبر", "دسامبر"];

const FA = "۰۱۲۳۴۵۶۷۸۹";

/** Any digits (Latin or Arabic-Indic) -> Persian digits. */
export function fa(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\d/g, (d) => FA[Number(d)]).replace(/[٠-٩]/g, (d) => FA["٠١٢٣٤٥٦٧٨٩".indexOf(d)]);
}

/** Persian digits (or Arabic-Indic) -> plain digits, for sending to the server. */
export function latin(value: string): string {
  return String(value).replace(/[۰-۹]/g, (d) => String(FA.indexOf(d))).replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
}

/** "1 ساعت 5 دقیقه" in Persian digits. */
export function fmtDuration(min: number | null | undefined): string {
  if (min === null || min === undefined) return "--";
  // round the total first: rounding only the remainder can produce "1 ساعت 60 دقیقه"
  const total = Math.round(min);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return fa(h > 0 ? `${h} ساعت ${m} دقیقه` : `${m} دقیقه`);
}

/** "h:mm" */
export function fmtHM(min: number): string {
  const t = Math.round(min);
  return fa(`${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`);
}

export function fmtPercent(p: number): string {
  return `${fa(String(Math.round(Math.abs(p) * 10) / 10).replace(".", "٫"))}٪`;
}

export function gregorianLabel(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${fa(d)} ${GREGORIAN_MONTHS[m - 1]} ${fa(y)}`;
}

/** Weekday name (Saturday-first list) of a Gregorian ISO date. */
export function weekdayOf(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return WEEKDAYS[(new Date(y, m - 1, d).getDay() + 1) % 7];
}

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function clockNow(): string {
  const n = new Date();
  return `${pad2(n.getHours())}:${pad2(n.getMinutes())}`;
}

/** Minutes between two "HH:MM" clock times (an end before the start wraps past midnight). */
export function spanMinutes(start: string, end: string): number {
  const [h1, m1] = start.split(":").map(Number);
  const [h2, m2] = end.split(":").map(Number);
  let diff = h2 * 60 + m2 - (h1 * 60 + m1);
  if (diff < 0) diff += 24 * 60;
  return diff;
}

// one fixed colour per tag, by the tag's position among all tags
const TAG_PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#84cc16", "#f97316", "#0f766e", "#a16207"];
export const NO_TAG_COLOR = "#94a3b8";

export function tagColor(tagId: number | string | null | undefined, allIds: number[]): string {
  if (tagId === null || tagId === undefined || tagId === "" || tagId === "none") return NO_TAG_COLOR;
  const sorted = [...allIds].sort((a, b) => a - b);
  const i = sorted.indexOf(Number(tagId));
  return TAG_PALETTE[(i < 0 ? Number(tagId) : i) % TAG_PALETTE.length];
}

/** Parse what a user typed into a time field: "930", "09:30", "۰۹۳۰", "9" -> HH:MM. */
export function parseTimeText(text: string): { state: "empty" | "ok" | "bad"; value: string } {
  const digits = latin(text).replace(/\D/g, "");
  if (!digits) return { state: "empty", value: "" };
  if (digits.length > 4) return { state: "bad", value: "" };
  const h = digits.length <= 2 ? Number(digits) : Number(digits.slice(0, digits.length - 2));
  const m = digits.length <= 2 ? 0 : Number(digits.slice(-2));
  if (h > 23 || m > 59) return { state: "bad", value: "" };
  return { state: "ok", value: `${pad2(h)}:${pad2(m)}` };
}
