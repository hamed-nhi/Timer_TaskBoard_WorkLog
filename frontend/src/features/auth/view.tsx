"use client";
import { useEffect, useState } from "react";
import { useMe } from "@/lib/data";
import { BrandMark } from "@/shared/brand";
import { Captcha } from "./captcha";
import { api, errorText } from "@/lib/api";

export default function LoginPage() {
  const { data: me, isLoading } = useMe();
  useEffect(() => { if (me) window.location.replace("/"); }, [me]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<{ captcha_provider: "none" | "arcaptcha"; site_key: string } | null>(null);
  const [configError, setConfigError] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [captchaNonce, setCaptchaNonce] = useState(0);
  async function loadConfig() {
    setConfigError(false);
    try { setConfig(await api("/api/auth/config")); }
    catch { setConfigError(true); }
  }
  useEffect(() => { void loadConfig(); }, []);


  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!config || (config.captcha_provider === "arcaptcha" && !captchaToken)) return;
    setError("");
    setBusy(true);
    setShowPassword(false);
    try {
      await api("/api/auth/login", "POST", { username, password, captcha_token: captchaToken });
      window.location.replace("/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
      setCaptchaToken("");
      setCaptchaNonce(n => n + 1);
    }
  }

  if (isLoading || me) return <div className="login-wrap" role="status">در حال بررسی ورود...</div>;

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand">
          <BrandMark />
          <div><h1>TIME LOG</h1><div className="brand-sub">ثبت ساعت کار روزانه</div></div>
        </div>
        <div className="stack">
          <div>
            <label className="lbl" htmlFor="u">نام کاربری</label>
            <input id="u" type="text" dir="ltr" autoComplete="username" autoCapitalize="none" autoCorrect="off" autoFocus required
              value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <div className="login-password-label">
              <label className="lbl" htmlFor="p">رمز عبور</label>
              <button className="btn btn-outline btn-sm" type="button" aria-controls="p" aria-pressed={showPassword}
                disabled={busy} onClick={() => setShowPassword(value => !value)}>{showPassword ? "پنهان‌کردن رمز" : "نمایش رمز"}</button>
            </div>
            <input id="p" type={showPassword ? "text" : "password"} dir="ltr" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {config?.captcha_provider === "arcaptcha" && <>
            <Captcha key={captchaNonce} siteKey={config.site_key} onToken={setCaptchaToken} />
            <button className="btn btn-outline" type="button" disabled={busy} onClick={() => { setCaptchaToken(""); setCaptchaNonce(n => n + 1); }}>دریافت دوباره کپچا</button>
          </>}
          {configError && <div role="alert">تنظیمات ورود دریافت نشد. <button type="button" className="btn btn-outline" onClick={loadConfig}>تلاش دوباره</button></div>}
          <div className="form-error" role="alert">{error}</div>
          <button className="btn btn-primary" type="submit" disabled={busy || !config || (config.captcha_provider === "arcaptcha" && !captchaToken)}>{busy ? "..." : "ورود"}</button>
          <div className="hint">حساب کاربری را مدیر سیستم برای شما می‌سازد. تلاش‌های ورود در سرور محدود می‌شوند؛ در صورت خطا، زمان انتظار نمایش داده می‌شود.</div>
        </div>
      </form>
    </div>
  );
}
