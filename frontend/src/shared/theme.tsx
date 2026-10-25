"use client";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { Icon } from "@/shared/icon";

type Choice = "system" | "light" | "dark";
const KEY = "timelog-theme";
const Theme = createContext<{ choice: Choice; dark: boolean; choose: (v: Choice) => void }>({ choice: "system", dark: false, choose: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoice] = useState<Choice>("system");
  const [dark, setDark] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const read = () => {
      try { const v = localStorage.getItem(KEY); setChoice(v === "light" || v === "dark" ? v : "system"); } catch { /* use device */ }
    };
    read(); setReady(true);
    const storage = (e: StorageEvent) => { if (e.key === KEY || e.key === null) read(); };
    window.addEventListener("storage", storage);
    return () => window.removeEventListener("storage", storage);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const isDark = choice === "dark" || (choice === "system" && media.matches);
      document.documentElement.dataset.theme = isDark ? "dark" : "light";
      setDark(isDark);
    };
    apply(); media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [choice, ready]);
  const choose = (value: Choice) => {
    setChoice(value);
    try { localStorage.setItem(KEY, value); } catch { /* still works for this page */ }
  };
  return <Theme.Provider value={{ choice, dark, choose }}>{children}</Theme.Provider>;
}

export function ThemeToggle() {
  const { dark, choose } = useContext(Theme);
  return <button type="button" className="theme-toggle" onClick={() => choose(dark ? "light" : "dark")} aria-label={dark ? "فعال‌کردن حالت روشن" : "فعال‌کردن حالت تیره"} title={dark ? "حالت روشن" : "حالت تیره"}><Icon name={dark ? "sun" : "moon"} /><span>{dark ? "حالت روشن" : "حالت تیره"}</span></button>;
}

export function ThemeSettings() {
  const { choice, choose } = useContext(Theme);
  return <section className="card appearance-card"><h2>ظاهر برنامه</h2><p className="hint">حالت دلخواهتان روی این مرورگر ذخیره می‌شود.</p><div className="theme-options" role="group" aria-label="انتخاب ظاهر برنامه">{([ ["light", "روشن", "sun"], ["dark", "تیره", "moon"], ["system", "همگام با دستگاه", "monitor"] ] as const).map(([value, label, icon]) => <button key={value} type="button" className={"theme-option" + (choice === value ? " selected" : "")} aria-pressed={choice === value} onClick={() => choose(value)}><Icon name={icon} />{label}</button>)}</div></section>;
}
