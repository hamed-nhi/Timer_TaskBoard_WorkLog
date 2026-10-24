"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { post, get } from "@/lib/api";
import { fmtDuration } from "@/lib/fa";
import { ClockProvider, liveMinutes, refreshAll, useClock, useMe, useTasks, useToday } from "@/lib/data";
import { Task } from "@/lib/types";
import { BrandMark } from "./brand";
import { FillProvider } from "./fill";
import { PresenceChip } from "./presence";
import { TagsProvider } from "./tags";
import { TaskDialogsProvider } from "./tasks";
import { Modal, UiProvider } from "./ui";

interface NavItem { href: string; label: string; icon: string; admin?: boolean }

const PRIMARY: NavItem[] = [
  { href: "/", label: "امروز", icon: "⏱" },
  { href: "/planned/", label: "برنامه‌ریزی", icon: "📝" },
  { href: "/dashboard/", label: "داشبورد", icon: "📊" },
];
const MORE: NavItem[] = [
  { href: "/calendar/", label: "تقویم", icon: "📅" },
  { href: "/timesheet/", label: "تایم‌شیت هفتگی", icon: "🗓" },
  { href: "/tasks/", label: "همه تسک‌ها", icon: "📋" },
  { href: "/daylog/", label: "گزارش روزانه", icon: "🧾" },
  { href: "/settings/", label: "تنظیمات", icon: "⚙" },
  { href: "/admin/", label: "مدیریت", icon: "👤" },
];
const PHONE: NavItem[] = [PRIMARY[0], PRIMARY[1], MORE[3], PRIMARY[2]];

const same = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <UiProvider>
      <ClockProvider>
        <TagsProvider>
          <TaskDialogsProvider>
            <FillProvider>
              <Frame>{children}</Frame>
            </FillProvider>
          </TaskDialogsProvider>
        </TagsProvider>
      </ClockProvider>
    </UiProvider>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { data: me, error } = useMe();
  const [moreOpen, setMoreOpen] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [resume, setResume] = useState(false);

  useEffect(() => { setMoreOpen(false); setSheet(false); }, [path]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName?.toLowerCase();
      if (["input", "select", "textarea"].includes(tag)) return;
      if (e.altKey && e.key.toLowerCase() === "r") { e.preventDefault(); setResume(true); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!moreOpen) return;
    const close = (e: MouseEvent) => { if (!(e.target as HTMLElement).closest(".tab-more")) setMoreOpen(false); };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [moreOpen]);

  if (error && (error as any).status !== 401) return <div className="app"><div className="card">ارتباط با سرور برقرار نشد. صفحه را دوباره باز کنید.</div></div>;
  if (!me) return null;

  const more = MORE.filter((i) => !i.admin || me.is_admin);
  const moreActive = more.find((i) => same(path, i.href));

  async function logout() {
    await post("/api/auth/logout");
    window.location.href = "/login/";
  }

  return (
    <div className="app">
      <header className="topbar">
        <Link href="/" className="brand">
          <BrandMark />
          <div><h1>تایم‌لاگ</h1><div className="brand-sub">ثبت ساعت کار روزانه</div></div>
        </Link>
        <div className="topbar-end">
          <PresenceChip />
          <span className="user-chip" title={me.username}>{me.display_name || me.username}</span>
        </div>
      </header>

      <nav className="tabs" aria-label="بخش‌های برنامه">
        {PRIMARY.map((i) => <Link key={i.href} href={i.href} className={"tab" + (same(path, i.href) ? " active" : "")}>{i.label}</Link>)}
        <div className="tab-more">
          <button type="button" className={"tab" + (moreActive ? " active" : "")} aria-haspopup="true" aria-expanded={moreOpen}
            onClick={(e) => { e.stopPropagation(); setMoreOpen(!moreOpen); }}>
            {moreActive ? moreActive.label : "بیشتر"} ▾
          </button>
          {moreOpen && (
            <div className="tab-menu">
              {more.map((i) => <Link key={i.href} href={i.href} className={"tab" + (same(path, i.href) ? " active" : "")}>{i.label}</Link>)}
              <button type="button" className="tab" onClick={() => { setMoreOpen(false); setResume(true); }}>ادامه سریع ▶</button>
              <button type="button" className="tab" onClick={logout}>خروج از حساب</button>
            </div>
          )}
        </div>
      </nav>

      <main>{children}</main>

      <RunningBar />
      <button type="button" className="fab" title="ادامه سریع (Alt+R)" onClick={() => setResume(true)}>▶</button>

      <nav className="bottom-nav" aria-label="ناوبری">
        {PHONE.map((i) => (
          <Link key={i.href} href={i.href} className={same(path, i.href) ? "active" : ""}>
            <span className="ico" aria-hidden="true">{i.icon}</span>{i.label}
          </Link>
        ))}
        <button type="button" className={moreActive && !PHONE.includes(moreActive) ? "active" : ""} onClick={() => setSheet(!sheet)}>
          <span className="ico" aria-hidden="true">☰</span>بیشتر
        </button>
      </nav>
      {sheet && (
        <div className="sheet-menu" onClick={() => setSheet(false)}>
          <div onClick={(e) => e.stopPropagation()}>
            {more.map((i) => <Link key={i.href} href={i.href} className={same(path, i.href) ? "active" : ""}>{i.icon} {i.label}</Link>)}
            <button onClick={() => { setSheet(false); setResume(true); }}>▶ ادامه سریع</button>
            <button onClick={logout}>خروج از حساب</button>
          </div>
        </div>
      )}
      {resume && <QuickResume onClose={() => setResume(false)} />}
    </div>
  );
}

/** Phone only: the running task stays visible (and stoppable) on every page. */
function RunningBar() {
  const { data: today } = useToday();
  const { data: tasks } = useTasks(today ? `year=${today.jalali_year}&month=${today.jalali_month}&day=${today.jalali_day}` : "");
  const now = useClock();
  const running = tasks?.find((t) => t.status === "running");
  if (!running) return null;
  const act = (fn: string) => async () => { await post(`/api/tasks/${running.id}/${fn}`); await refreshAll(); };
  return (
    <div className="running-bar" role="status">
      <span className="live-dot" />
      <span className="rb-title">{running.title}</span>
      <span className="rb-time">{fmtDuration(liveMinutes(running, now))}</span>
      <button className="act-btn pause-btn" onClick={act("pause")}>⏸</button>
      <button className="act-btn stop-btn" onClick={act("stop")}>⏹</button>
    </div>
  );
}

function QuickResume({ onClose }: { onClose: () => void }) {
  const [paused, setPaused] = useState<Task[] | null>(null);
  const [last, setLast] = useState<Task | null>(null);
  useEffect(() => {
    Promise.all([get<Task[]>("/api/tasks/paused"), get<Task[]>("/api/tasks")]).then(([p, all]) => {
      setPaused(p);
      setLast(all.filter((t) => t.status === "done").sort((a, b) => b.id - a.id)[0] || null);
    });
  }, []);
  return (
    <Modal onClose={onClose}>
      <h2>ادامه سریع</h2>
      {paused === null && <div className="empty-hint">...</div>}
      {paused && paused.length > 0 && <div className="quick-resume-section-title">تسک‌های مکث‌شده</div>}
      {paused?.map((t) => (
        <div className="quick-resume-item" key={t.id}>
          <span>{t.title} ({fmtDuration(t.accumulated_minutes)})</span>
          <button className="act-btn resume-btn" onClick={async () => { await post(`/api/tasks/${t.id}/resume`); onClose(); await refreshAll(); }}>ادامه ▶</button>
        </div>
      ))}
      {last && (
        <>
          <div className="quick-resume-section-title">شروع دوباره آخرین تسک تمام‌شده</div>
          <div className="quick-resume-item">
            <span>{last.title}</span>
            <button className="act-btn start-planned-btn" onClick={async () => {
              await post("/api/tasks", { title: last.title, tag_id: last.tag_id || undefined });
              onClose();
              await refreshAll();
            }}>شروع ▶</button>
          </div>
        </>
      )}
      {paused && !paused.length && !last && <div className="empty-hint">هنوز تسک مکث‌شده یا تمام‌شده‌ای نیست</div>}
      <div className="modal-actions"><div className="spacer" /><button className="btn btn-outline" onClick={onClose}>بستن</button></div>
    </Modal>
  );
}
