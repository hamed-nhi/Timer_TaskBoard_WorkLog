"use client";
import { useEffect, useId, useRef, useState } from "react";

type CaptchaApi = { render: (selector: string, options: Record<string, unknown>) => unknown };
declare global { interface Window { arcaptcha?: CaptchaApi } }

export function Captcha({ siteKey, onToken }: { siteKey: string; onToken: (token: string) => void }) {
  const id = "captcha-" + useId().replace(/[^a-zA-Z0-9-]/g, "");
  const container = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    const script = document.createElement("script");
    const fail = () => { if (active) { onToken(""); setFailed(true); } };
    const render = () => {
      if (!active) return;
      try {
        if (!window.arcaptcha) { fail(); return; }
        window.arcaptcha.render("#" + id, { site_key: siteKey, lang: "fa",
          callback: (token: unknown) => { if (active) { onToken(typeof token === "string" ? token : ""); setFailed(false); } },
          expired_callback: () => { if (active) onToken(""); }, error_callback: fail });
      } catch { fail(); }
    };
    if (window.arcaptcha) render();
    else { script.src = "https://nwidget.arcaptcha.ir/1/api.js"; script.async = true; script.onload = render; script.onerror = fail; document.head.appendChild(script); }
    const timeout = setTimeout(() => { if (!window.arcaptcha) fail(); }, 15000);
    const node = container.current;
    return () => { active = false; clearTimeout(timeout); script.remove(); if (node) node.innerHTML = ""; };
  }, [id, siteKey, onToken]);
  return <div className="captcha-wrap"><div ref={container} id={id} aria-label="تأیید انسان بودن" />
    {failed && <p className="form-error" role="alert">کپچا بارگیری نشد؛ اتصال اینترنت را بررسی و دوباره تلاش کنید.</p>}</div>;
}
