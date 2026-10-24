"use client";
import { useState } from "react";
import useSWR, { mutate } from "swr";
import { del, errorText, fetcher, post, put } from "@/lib/api";
import { fa } from "@/lib/fa";
import { refreshAll, useMe } from "@/lib/data";
import { AdminUser } from "@/lib/types";
import { useUi } from "@/components/ui";

interface AdminCatalog {
  types: { id: number; name: string }[];
  projects: { id: number; name: string; stories: { id: number; name: string }[] }[];
}

export default function AdminPage() {
  const { data: me } = useMe();
  if (!me) return null;
  return (
    <>
      {me.is_admin && <Users />}
      <Catalog />
    </>
  );
}

function Users() {
  const { toast, confirm } = useUi();
  const { data: users = [], mutate: reload } = useSWR<AdminUser[]>("/api/admin/users", fetcher);
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [error, setError] = useState("");
  const [temp, setTemp] = useState<{ user: string; password: string } | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await post("/api/admin/users", { username, display_name: name, is_admin: isAdmin });
      setTemp({ user: r.username, password: r.temp_password });
      setUsername(""); setName(""); setIsAdmin(false);
      await reload();
    } catch (err) { setError(errorText(err)); }
  }
  async function reset(u: AdminUser) {
    if (!(await confirm(`رمز «${u.username}» دوباره ساخته شود؟ او از همه‌ی دستگاه‌ها خارج می‌شود.`, "بله، بساز"))) return;
    const r = await post(`/api/admin/users/${u.id}/reset-password`);
    setTemp({ user: u.username, password: r.temp_password });
  }
  async function toggle(u: AdminUser) {
    try { await put(`/api/admin/users/${u.id}`, { is_active: !u.is_active }); await reload(); } catch (err) { toast(errorText(err)); }
  }

  return (
    <div className="card">
      <h2>کاربران</h2>
      {temp && (
        <div className="presence-note">
          رمز موقت «{temp.user}»: <b dir="ltr" style={{ userSelect: "all" }}>{temp.password}</b> — این رمز فقط همین یک بار نشان داده می‌شود؛ آن را امن برای کاربر بفرستید.
          <button className="btn btn-outline btn-sm" style={{ marginInlineStart: 8 }} onClick={() => setTemp(null)}>بستن</button>
        </div>
      )}
      <div className="table-scroll">
        <table className="user-table">
          <thead><tr><th>نام کاربری</th><th>نام</th><th>نقش</th><th>وضعیت</th><th /></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td dir="ltr" style={{ textAlign: "start" }}>{u.username}</td>
                <td>{u.display_name}</td>
                <td>{u.is_admin ? <span className="badge">مدیر</span> : "کاربر"}</td>
                <td>{u.is_active ? "فعال" : <span className="badge off">غیرفعال</span>}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="btn btn-outline btn-sm" onClick={() => reset(u)}>رمز جدید</button>{" "}
                  <button className="btn btn-outline btn-sm" onClick={() => toggle(u)}>{u.is_active ? "غیرفعال کن" : "فعال کن"}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="stack" onSubmit={create} style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
        <div className="row2">
          <input type="text" dir="ltr" placeholder="نام کاربری (حروف لاتین کوچک)" autoCapitalize="none" required value={username} onChange={(e) => setUsername(e.target.value)} />
          <input type="text" placeholder="نام نمایشی" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <label className="finish-check"><input type="checkbox" checked={isAdmin} onChange={(e) => setIsAdmin(e.target.checked)} /> مدیر باشد</label>
        <div className="form-error">{error}</div>
        <button className="btn btn-primary" type="submit">ساخت کاربر (رمز موقت ساخته می‌شود)</button>
      </form>
    </div>
  );
}

function Catalog() {
  const { toast, confirm } = useUi();
  const { data, mutate: reload } = useSWR<AdminCatalog>("/api/catalog", fetcher);
  const [newType, setNewType] = useState("");
  const [newProject, setNewProject] = useState("");
  const [newStory, setNewStory] = useState<Record<number, string>>({});
  if (!data) return null;

  const done = async () => { await reload(); await mutate("/api/company-catalog"); await refreshAll(); };
  const run = async (fn: () => Promise<unknown>) => { try { await fn(); await done(); } catch (e) { toast(errorText(e)); } };
  const rename = async (url: string, current: string) => {
    const name = window.prompt("نام جدید:", current);
    if (name && name.trim() && name !== current) await run(() => put(url, { name: name.trim() }));
  };
  const remove = async (url: string, label: string) => {
    if (await confirm(`«${label}» حذف شود؟`)) await run(() => del(url));
  };

  return (
    <div className="card">
      <h2>نوع گزارش، پروژه و استوری‌های من</h2>
      <div className="hint" style={{ marginBottom: 10 }}>این فهرست فقط متعلق به حساب شماست. نوع گزارش، پروژه و استوری جدید بسازید و در «ویرایش تگ‌ها» انتخاب کنید. دیگران به این موارد دسترسی ندارند. مورد استفاده‌شده روی تگ یا تسک حذف نمی‌شود.</div>

      <div className="tag-sub-title">نوع گزارش</div>
      {data.types.map((t) => (
        <div className="catalog-item" key={t.id}>
          <span style={{ flex: 1 }}>{t.name}</span>
          <button className="btn btn-outline btn-sm" onClick={() => rename(`/api/catalog/report-types/${t.id}`, t.name)}>تغییر نام</button>
          <button className="btn btn-danger btn-sm" onClick={() => remove(`/api/catalog/report-types/${t.id}`, t.name)}>حذف</button>
        </div>
      ))}
      <div className="tags-add">
        <input type="text" placeholder="نوع گزارش جدید..." value={newType} onChange={(e) => setNewType(e.target.value)} />
        <button className="btn btn-primary" onClick={() => newType.trim() && run(async () => { await post("/api/catalog/report-types", { name: newType.trim() }); setNewType(""); })}>افزودن</button>
      </div>

      <div className="tag-sub-title">پروژه‌ها و استوری‌ها</div>
      {data.projects.map((p) => (
        <div key={p.id} style={{ marginBottom: 12 }}>
          <div className="catalog-item">
            <b style={{ flex: 1 }}>{p.name} <span className="hint">({fa(p.stories.length)} استوری)</span></b>
            <button className="btn btn-outline btn-sm" onClick={() => rename(`/api/catalog/projects/${p.id}`, p.name)}>تغییر نام</button>
            <button className="btn btn-danger btn-sm" onClick={() => remove(`/api/catalog/projects/${p.id}`, p.name)}>حذف</button>
          </div>
          {p.stories.map((s) => (
            <div className="catalog-item catalog-story" key={s.id}>
              <span style={{ flex: 1 }}>{s.name}</span>
              <button className="btn btn-outline btn-sm" onClick={() => rename(`/api/catalog/stories/${s.id}`, s.name)}>تغییر نام</button>
              <button className="btn btn-danger btn-sm" onClick={() => remove(`/api/catalog/stories/${s.id}`, s.name)}>حذف</button>
            </div>
          ))}
          <div className="tags-add catalog-story" style={{ borderTop: 0, paddingTop: 4 }}>
            <input type="text" placeholder="استوری جدید برای این پروژه..." value={newStory[p.id] || ""} onChange={(e) => setNewStory({ ...newStory, [p.id]: e.target.value })} />
            <button className="btn btn-outline" onClick={() => (newStory[p.id] || "").trim() && run(async () => {
              await post(`/api/catalog/projects/${p.id}/stories`, { name: newStory[p.id].trim() });
              setNewStory({ ...newStory, [p.id]: "" });
            })}>افزودن</button>
          </div>
        </div>
      ))}
      <div className="tags-add">
        <input type="text" placeholder="پروژه‌ی جدید..." value={newProject} onChange={(e) => setNewProject(e.target.value)} />
        <button className="btn btn-primary" onClick={() => newProject.trim() && run(async () => { await post("/api/catalog/projects", { name: newProject.trim() }); setNewProject(""); })}>افزودن پروژه</button>
      </div>
    </div>
  );
}
