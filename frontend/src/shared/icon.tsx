import { CSSProperties } from "react";

const paths: Record<string, React.ReactNode> = {
  today: <><circle cx="12" cy="13" r="8" /><path d="M12 9v4l3 2M9 2h6M12 2v3" /></>,
  planned: <><rect x="4" y="5" width="16" height="16" rx="3" /><path d="M8 3v4M16 3v4M4 10h16m-11 5 2 2 4-4" /></>,
  daylog: <><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" /><path d="M14 3v6h6M8 13h8M8 17h5" /></>,
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="11" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="18" width="7" height="3" rx="1" /></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="3" /><path d="M7 3v4M17 3v4M3 11h18M8 15h1M15 15h1M8 18h1" /></>,
  timesheet: <><rect x="3" y="4" width="18" height="17" rx="3" /><path d="M3 10h18M9 10v11M15 10v11M3 15h18" /></>,
  tasks: <><path d="m3 6 1 1 2-2m-3 7 1 1 2-2m-3 7 1 1 2-2M10 6h11M10 12h11M10 18h11" /></>,
  settings: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></>,
  admin: <><path d="M3 21v-2a5 5 0 0 1 5-5h8a5 5 0 0 1 5 5v2" /><circle cx="12" cy="6" r="4" /></>,
  moon: <path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.4 1.4M17.6 17.6 19 19M19 5l-1.4 1.4M6.4 17.6 5 19" /></>,
  monitor: <><rect x="3" y="3" width="18" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>,
  more: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></>,
};
export function Icon({ name, size = 20, style }: { name: string; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name] || paths.tasks}</svg>;
}
