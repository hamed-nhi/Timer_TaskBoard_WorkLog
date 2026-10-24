"use client";
// Shared server data (SWR) and a one-second clock for live timers.
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { fetcher } from "@/lib/api";
import { Catalog, GoalProgress, Me, Planned, Presence, Settings, Tag, Task, Today } from "@/lib/types";
import { tagColor } from "@/lib/format";

export function useMe() {
  return useSWR<Me>("/api/me", fetcher, { shouldRetryOnError: false, revalidateOnFocus: false });
}

// Times from the server are naive Tehran wall-clock times. The browser may be in another time zone,
// so remember how far its clock is from the server's wall clock and correct every elapsed-time sum.
let SKEW = 0;

export function useToday() {
  return useSWR<Today & { server_time: string }>("/api/today", fetcher, {
    refreshInterval: 60_000, revalidateOnFocus: true,
    onSuccess: (d) => { SKEW = new Date(d.server_time).getTime() - Date.now(); },
  });
}

/** Browser "now" expressed on the server's wall clock, as a Date whose local fields are Tehran time. */
export const serverNow = (now: number) => new Date(now + SKEW);

/** "HH:MM" on the server's wall clock (Tehran), whatever time zone the browser is in. */
export function serverClock(now = Date.now()): string {
  const d = serverNow(now);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export const useTags = () => useSWR<Tag[]>("/api/tags", fetcher, { revalidateOnFocus: true });
export const useCatalog = () => useSWR<Catalog>("/api/company-catalog", fetcher, { revalidateOnFocus: false });
export const useSettings = () => useSWR<Settings>("/api/settings", fetcher);
export const useGoals = () => useSWR<GoalProgress>("/api/goal-progress", fetcher, { refreshInterval: 60_000 });
export const usePresence = () => useSWR<Presence>("/api/presence", fetcher, { refreshInterval: 30_000 });
export const usePlanned = () => useSWR<Planned[]>("/api/planned", fetcher);

export function useTasks(query: string) {
  return useSWR<Task[]>(query ? `/api/tasks?${query}` : null, fetcher, { revalidateOnFocus: true });
}

/** Refresh everything that shows tasks, tags, presence or plans after a change. */
export function refreshAll() {
  return globalMutate((key) => typeof key === "string" && key.startsWith("/api/") && key !== "/api/me" && key !== "/api/today");
}

/* ---- the clock: one timer for the whole app ---- */

const ClockCtx = createContext(0);
export const useClock = () => useContext(ClockCtx);

export function ClockProvider({ children }: { children: ReactNode }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = () => { if (!document.hidden) setNow(Date.now()); };
    const id = setInterval(tick, 1000);
    document.addEventListener("visibilitychange", tick);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", tick); };
  }, []);
  return <ClockCtx.Provider value={now}>{children}</ClockCtx.Provider>;
}

/** Minutes worked on a task so far, ticking while it runs. */
export function liveMinutes(task: Task, now: number): number {
  let total = task.accumulated_minutes || 0;
  if (task.status === "running" && task.segment_started_at) {
    total += Math.max(0, (now + SKEW - new Date(task.segment_started_at).getTime()) / 60000);
  }
  return total;
}

export function useTagColor() {
  const { data } = useTags();
  const ids = (data || []).map((t) => t.id);
  return (id: number | string | null | undefined) => tagColor(id, ids);
}
