// The daily-log page opens on a day chosen elsewhere (timesheet, calendar); remember it for this tab only.
export interface DayRef { year: number; month: number; day: number; gregorian: string }

const KEY = "daylogDay";

export function setDaylogDay(d: DayRef) {
  try { sessionStorage.setItem(KEY, JSON.stringify(d)); } catch { /* storage unavailable */ }
}

export function takeDaylogDay(): DayRef | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as DayRef) : null;
  } catch { return null; }
}
