"use client";
import { useEffect, useState } from "react";
import { useMe } from "@/lib/data";
import { BrandMark } from "@/components/brand";
import { api, errorText } from "@/lib/api";

export default function LoginPage() {
  const { data: me, isLoading } = useMe();
  useEffect(() => { if (me) window.location.replace("/"); }, [me]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/api/auth/login", "POST", { username, password });
      window.location.replace("/");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  if (isLoading || me) return <div className="login-wrap" role="status">در حال بررسی ورود...</div>;

  return (
    <div className="login-wrap">
      <form className="card login-card" onSubmit={submit}>
        <div className="brand">
          <BrandMark />
          <div><h1>تایم‌لاگ</h1><div className="brand-sub">ثبت ساعت کار روزانه</div></div>
        </div>
        <div className="stack">
          <div>
            <label className="lbl" htmlFor="u">نام کاربری</label>
            <input id="u" type="text" dir="ltr" autoComplete="username" autoCapitalize="none" autoCorrect="off" autoFocus required
              value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label className="lbl" htmlFor="p">رمز عبور</label>
            <input id="p" type="password" dir="ltr" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div className="form-error" role="alert">{error}</div>
          <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "..." : "ورود"}</button>
          <div className="hint">حساب کاربری را مدیر سیستم برای شما می‌سازد. بعد از ۳ بار رمز اشتباه، ۲۰ دقیقه امکان تلاش مجدد نیست.</div>
        </div>
      </form>
    </div>
  );
}
