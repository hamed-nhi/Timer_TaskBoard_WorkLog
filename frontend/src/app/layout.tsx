import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeProvider } from "@/shared/theme";

export const metadata: Metadata = {
  title: "تایم‌لاگ",
  description: "ثبت ساعت کار روزانه",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/favicon.png", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "تایم‌لاگ", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#4f46e5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('timelog-theme');document.documentElement.dataset.theme=(p==='dark'||(p!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches))?'dark':'light'}catch(e){document.documentElement.dataset.theme=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}})()` }} /></head>
      <body><ThemeProvider>{children}</ThemeProvider></body>
    </html>
  );
}
