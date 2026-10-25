"use client";
import Link from "next/link";
import { SWRConfig } from "swr";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { post, get } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { ClockProvider, liveMinutes, refreshAll, useClock, useMe, useTasks, useToday } from "@/lib/data";
import { Task } from "@/lib/types";
import { Icon } from "@/shared/icon";
import { ThemeToggle } from "@/shared/theme";
import { BrandMark } from "@/shared/brand";
import { BackupSetupGate } from "@/features/settings/backup-setup";
import { FillProvider } from "@/features/fill/components";
import { PresenceChip } from "@/features/presence/components";
import { TagsProvider } from "@/features/tags/components";
import { TaskDialogsProvider } from "@/features/tasks/components";
import { Modal, UiProvider } from "@/shared/ui";

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
    <SWRConfig value={{ refreshInterval: 15_000, revalidateOnFocus: true, revalidateOnReconnect: true }}>
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
    </SWRConfig>
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
  const current = [...PRIMARY, ...MORE].find((i) => same(path, i.href));
  const iconName = (i: NavItem) => i.href === "/" ? "today" : i.href.split("/")[1];
  const navGroups = [
    { label: "کارهای روزانه", items: [PRIMARY[0], PRIMARY[1], MORE[2]] },
    { label: "گزارش و تحلیل", items: [MORE[3], PRIMARY[2], MORE[0], MORE[1]] },
    { label: "حساب من", items: [MORE[5], MORE[4]] },
  ];

  async function logout() {
    await post("/api/auth/logout");
    window.location.href = "/login/";
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main-content">رفتن به محتوای صفحه</a>
      <aside className="sidebar">
        <Link href="/" className="brand sidebar-brand"><BrandMark /><div><h1>TIME LOG</h1><span className="brand-sub">زمانت، روشن و مرتب</span></div></Link>
        <nav aria-label="ناوبری اصلی" className="side-nav">
          {navGroups.map((group) => <div className="nav-group" key={group.label}><div className="nav-group-label">{group.label}</div>{group.items.map((i) => <Link key={i.href} href={i.href} aria-current={same(path, i.href) ? "page" : undefined} className={"side-link" + (same(path, i.href) ? " active" : "")}><Icon name={iconName(i)} /><span>{i.label}</span></Link>)}</div>)}
        </nav>
        <div className="sidebar-foot"><button type="button" className="side-link" onClick={() => setResume(true)}><Icon name="today" />ادامه سریع<span className="key-hint">Alt R</span></button><button type="button" className="side-link" onClick={logout}><Icon name="logout" />خروج از حساب</button></div>
      </aside>
      <header className="topbar">
        <Link href="/" className="brand mobile-brand">
          <BrandMark />
          <div><h1>TIME LOG</h1><div className="brand-sub">ثبت ساعت کار روزانه</div></div>
        </Link>
        <div className="page-heading"><div className="eyebrow">فضای کار شخصی</div><h2>{current?.label || "TIME LOG"}</h2></div>
        <div className="topbar-end">
          <ThemeToggle />
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

      <main id="main-content" className="app-main" tabIndex={-1}><BackupSetupGate>{children}</BackupSetupGate></main>

      <RunningBar />
      <button type="button" className="fab" title="ادامه سریع (Alt+R)" onClick={() => setResume(true)}>▶</button>

      <nav className="bottom-nav" aria-label="ناوبری">
        {PHONE.map((i) => (
          <Link key={i.href} href={i.href} aria-current={same(path, i.href) ? "page" : undefined} className={same(path, i.href) ? "active" : ""}>
            <span className="ico" aria-hidden="true"><Icon name={iconName(i)} /></span>{i.label}
          </Link>
        ))}
        <button type="button" aria-expanded={sheet} aria-controls="mobile-more" className={moreActive && !PHONE.includes(moreActive) ? "active" : ""} onClick={() => setSheet(!sheet)}>
          <span className="ico" aria-hidden="true"><Icon name="more" /></span>بیشتر
        </button>
      </nav>
      {sheet && (
        <div id="mobile-more" className="sheet-menu" onClick={() => setSheet(false)}>
          <div onClick={(e) => e.stopPropagation()}>
            {more.map((i) => <Link key={i.href} href={i.href} aria-current={same(path, i.href) ? "page" : undefined} className={same(path, i.href) ? "active" : ""}>{i.icon} {i.label}</Link>)}
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
      <button aria-label="مکث تسک فعال" className="act-btn pause-btn" onClick={act("pause")}>⏸</button>
      <button aria-label="پایان تسک فعال" className="act-btn stop-btn" onClick={act("stop")}>⏹</button>
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
