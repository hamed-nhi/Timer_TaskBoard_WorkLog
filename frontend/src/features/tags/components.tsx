"use client";
import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import useSWR, { mutate } from "swr";
import { del, errorText, fetcher, post, put } from "@/lib/api";
import { fa, fmtHM } from "@/lib/format";
import { Catalog, Tag } from "@/lib/types";
import { refreshAll, useCatalog, useTags } from "@/lib/data";
import { BudgetBar, budgetText, Modal, useUi } from "@/shared/ui";

/* ---------- tag picker (stories grouped under their project) ---------- */

const NEW = "__new__";
const MANAGE = "__manage__";

interface TagsCtx {
  openManager: () => void;
  askNewTag: () => Promise<Tag | null>;
}
const Ctx = createContext<TagsCtx>({ openManager: () => {}, askNewTag: async () => null });
export const useTagActions = () => useContext(Ctx);

export function TagSelect({ value, onChange, id }: { value: number | null; onChange: (v: number | null) => void; id?: string }) {
  const { data: tags = [] } = useTags();
  const { askNewTag, openManager } = useTagActions();
  const groups = new Map<string, Tag[]>();
  tags.forEach((t) => {
    const key = t.project || "سایر (بدون پروژه)";
    groups.set(key, [...(groups.get(key) || []), t]);
  });
  const keys = [...groups.keys()].sort((a, b) => Number(a.startsWith("سایر (بدون")) - Number(b.startsWith("سایر (بدون")));

  async function change(v: string) {
    if (v === MANAGE) return openManager();
    if (v === NEW) {
      const created = await askNewTag();
      if (created) onChange(created.id);
      return;
    }
    onChange(v ? Number(v) : null);
  }

  return (
    <select id={id} aria-label="عنوان استوری" value={value ?? ""} onChange={(e) => change(e.target.value)}>
      <option value="">(بدون استوری)</option>
      {keys.map((k) => (
        <optgroup key={k} label={k}>
          {groups.get(k)!.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </optgroup>
      ))}
      <option value={NEW}>+ افزودن استوری جدید...</option>
      <option value={MANAGE}>✎ ویرایش استوری‌ها...</option>
    </select>
  );
}

/* ---------- provider: new-tag dialog + tag manager ---------- */

export function TagsProvider({ children }: { children: ReactNode }) {
  const [manager, setManager] = useState(false);
  const [newTag, setNewTag] = useState<{ resolve: (t: Tag | null) => void } | null>(null);

  const ctx: TagsCtx = {
    openManager: () => setManager(true),
    askNewTag: () => new Promise((resolve) => setNewTag({ resolve })),
  };
  return (
    <Ctx.Provider value={ctx}>
      {children}
      {newTag && <NewTagDialog onDone={(t) => { newTag.resolve(t); setNewTag(null); }} />}
      {manager && <TagManager onClose={() => setManager(false)} />}
    </Ctx.Provider>
  );
}

function StoryPicker({ catalog, value, onChange }: { catalog?: Catalog; value: number | null; onChange: (id: number | null, name: string) => void }) {
  return (
    <select aria-label="استوری سامانه‌ی اصلی" value={value ?? ""} onChange={(e) => {
      const id = e.target.value ? Number(e.target.value) : null;
      const story = catalog?.projects.flatMap((p) => p.stories).find((s) => s.id === id);
      onChange(id, story?.name || "");
    }}>
      <option value="">— بدون استوری —</option>
      {catalog?.projects.map((p) => (
        <optgroup key={p.id} label={p.name}>{p.stories.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</optgroup>
      ))}
    </select>
  );
}

function NewTagDialog({ onDone }: { onDone: (t: Tag | null) => void }) {
  const { data: catalog } = useCatalog();
  const [name, setName] = useState("");
  const [budget, setBudget] = useState("");
  const [story, setStory] = useState<number | null>(null);
  const [type, setType] = useState("");
  const [error, setError] = useState("");

  async function create() {
    if (!name.trim()) return setError("نام تگ را بنویسید");
    try {
      const tag = await post<Tag>("/api/tags", {
        name: name.trim(), budget_hours: budget.trim() === "" ? null : Number(budget),
        story_id: story, report_type_id: type ? Number(type) : null,
      });
      await mutate("/api/tags");
      onDone(tag);
    } catch (e) { setError(errorText(e)); }
  }

  return (
    <Modal onClose={() => onDone(null)}>
      <h2>تگ جدید (عنوان استوری)</h2>
      <label className="lbl">نام تگ</label>
      <input type="text" maxLength={60} autoFocus value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
      <label className="lbl">استوری در سامانه‌ی اصلی <span className="optional">— اختیاری</span></label>
      <StoryPicker catalog={catalog} value={story} onChange={(id, n) => { setStory(id); if (id && !name.trim()) setName(n.slice(0, 60)); }} />
      <label className="lbl">نوع گزارش <span className="optional">— اختیاری</span></label>
      <select aria-label="نوع گزارش" value={type} onChange={(e) => setType(e.target.value)}>
        <option value="">—</option>
        {catalog?.types.filter((t) => t.id).map((t) => <option key={t.id} value={t.id!}>{t.name}</option>)}
      </select>
      <label className="lbl">بودجه‌ی زمانی کل (ساعت) <span className="optional">— اختیاری</span></label>
      <input type="number" min={0} step={0.5} inputMode="decimal" placeholder="مثلاً ۲۰۰" value={budget} onChange={(e) => setBudget(e.target.value)} />
      <div className="form-error">{error}</div>
      <div className="modal-actions">
        <div className="spacer" />
        <button className="btn btn-outline" onClick={() => onDone(null)}>انصراف</button>
        <button className="btn btn-primary" onClick={create}>ساخت تگ</button>
      </div>
    </Modal>
  );
}

/* ---------- tag manager ---------- */

const sameName = (a: string, b: string) => {
  const norm = (x: string) => x.trim().replace(/ي/g, "ی").replace(/ك/g, "ک").replace(/ى/g, "ی").toLowerCase();
  return norm(a) === norm(b);
};

export function TagManager({ onClose }: { onClose: () => void }) {
  const { confirm, toast } = useUi();
  const { data: tags = [], mutate: reload } = useSWR<Tag[]>("/api/tags?usage=1", fetcher);
  const { data: catalog } = useCatalog();
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [newBudget, setNewBudget] = useState("");

  const changed = async () => { await reload(); await refreshAll(); };

  async function add() {
    const name = newName.trim();
    if (!name) return;
    setError("");
    try {
      await post("/api/tags", { name, budget_hours: newBudget.trim() === "" ? null : Number(newBudget) });
      setNewName(""); setNewBudget("");
      await changed();
    } catch (e) { setError(errorText(e)); }
  }

  return (
    <Modal onClose={onClose} className="modal-wide">
      <h2>ویرایش تگ‌ها (عنوان استوری‌ها)</h2>
      <div className="hint">نام هر تگ را عوض کنید و «ذخیره» بزنید؛ تسک‌های قبلی با همان تگ می‌مانند و فقط نامش در همه‌جا عوض می‌شود. فقط تگی که روی هیچ تسکی نیست قابل حذف است.</div>
      <details className="how-to">
        <summary>راهنمای بودجه‌ی ساعت</summary>
        <ul>
          <li>زیر هر تگ، تخمین ساعت کار آن را بنویسید (مثلاً ۵۰) و «ثبت بودجه» بزنید.</li>
          <li>«کل سابقه‌ی تگ» ساعت‌های قبلی را هم می‌شمارد؛ «از امروز» فقط کار از امروز به بعد را.</li>
          <li>نوار پیشرفت (سبز، از ۸۰٪ نارنجی، بالای ۱۰۰٪ قرمز) همین‌جا و در «داشبورد» دیده می‌شود.</li>
        </ul>
      </details>
      <div className="stack" style={{ margin: "12px 0" }}>
        {!tags.length && <div className="empty-hint">هنوز تگی ندارید</div>}
        {tags.map((t) => (
          <TagBlock key={t.id} tag={t} all={tags} catalog={catalog} changed={changed} setError={setError}
            confirm={confirm} toast={toast} />
        ))}
      </div>
      <div className="tags-add">
        <input type="text" placeholder="تگ جدید..." aria-label="نام تگ جدید" maxLength={60} value={newName} onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()} />
        <input type="number" min={0} step={0.5} inputMode="decimal" placeholder="بودجه (ساعت) - اختیاری" aria-label="بودجه‌ی تگ جدید"
          value={newBudget} onChange={(e) => setNewBudget(e.target.value)} />
        <button className="btn btn-primary" onClick={add}>افزودن</button>
      </div>
      <div className="form-error">{error}</div>
      <div className="modal-actions"><div className="spacer" /><button className="btn btn-outline" onClick={onClose}>بستن</button></div>
    </Modal>
  );
}

function TagBlock({ tag, all, catalog, changed, setError, confirm, toast }: {
  tag: Tag; all: Tag[]; catalog?: Catalog; changed: () => Promise<void>; setError: (s: string) => void;
  confirm: (m: string, y?: string) => Promise<boolean>; toast: (m: string) => void;
}) {
  const [name, setName] = useState(tag.name);
  useEffect(() => setName(tag.name), [tag.name]);
  const used = (tag.task_count || 0) + (tag.planned_count || 0) + (tag.archived_count || 0);

  async function save() {
    const n = name.trim();
    if (!n || n === tag.name) return;
    setError("");
    const clash = all.find((o) => o.id !== tag.id && sameName(o.name, n));
    try {
      if (clash) {
        // the new name already belongs to another tag: offer to merge instead of refusing
        const ok = await confirm(
          `تگی با نام «${clash.name}» از قبل هست. تگ «${tag.name}» در آن ادغام شود؟ ${fa(used)} مورد از «${tag.name}» به «${clash.name}» منتقل می‌شود و تگ «${tag.name}» حذف می‌شود. هیچ زمانی از بین نمی‌رود.`,
          "بله، ادغام کن");
        if (!ok) return;
        const r = await post(`/api/tags/${tag.id}/merge`, { into: clash.id });
        toast(`«${tag.name}» در «${clash.name}» ادغام شد (${fa(r.moved_tasks)} تسک منتقل شد)`);
      } else {
        await put(`/api/tags/${tag.id}`, { name: n });
        toast(`نام تگ به «${n}» تغییر کرد`);
      }
      await changed();
    } catch (e) { setError(errorText(e)); }
  }

  async function remove() {
    if (!(await confirm(`تگ «${tag.name}» حذف شود؟ (روی هیچ تسکی استفاده نشده)`))) return;
    try { await del(`/api/tags/${tag.id}`); await changed(); } catch (e) { setError(errorText(e)); }
  }

  return (
    <div className="tag-edit-block">
      <div className="tag-edit-row">
        <input type="text" maxLength={60} aria-label={`نام تگ ${tag.name}`} value={name} onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && save()} />
        <button className="btn btn-primary btn-sm" style={{ visibility: name.trim() && name.trim() !== tag.name ? "visible" : "hidden" }} onClick={save}>ذخیره</button>
        <button className="btn btn-danger btn-sm" disabled={used > 0} title={used ? "این تگ روی تسک‌ها استفاده شده و قابل حذف نیست" : "حذف تگ بدون استفاده"} onClick={remove}>حذف</button>
        <span className="tag-usage">{used ? `${fa(tag.task_count)} تسک${tag.planned_count ? ` · ${fa(tag.planned_count)} برنامه` : ""}` : "استفاده نشده"}</span>
      </div>
      <BudgetEditor tag={tag} onSaved={changed} toast={toast} />
      <CompanyEditor tag={tag} catalog={catalog} onSaved={changed} toast={toast} />
    </div>
  );
}

function BudgetEditor({ tag, onSaved, toast }: { tag: Tag; onSaved: () => Promise<void>; toast: (m: string) => void }) {
  const savedMode = tag.budget_since ? "today" : "all";
  const [hours, setHours] = useState(tag.budget_minutes ? String(Math.round((tag.budget_minutes / 60) * 100) / 100) : "");
  const [from, setFrom] = useState(savedMode);
  const [msg, setMsg] = useState("");

  async function save() {
    setMsg("");
    // when only the number changes keep the stored start day; "today" is applied only if just chosen
    const mode = tag.budget_minutes && from === savedMode ? "keep" : from;
    try {
      await put(`/api/tags/${tag.id}/budget`, { hours: hours.trim() === "" ? null : Number(hours), from: mode });
      toast(hours.trim() === "" ? `بودجه‌ی «${tag.name}» برداشته شد` : `بودجه‌ی «${tag.name}» ثبت شد`);
      await onSaved();
    } catch (e) { setMsg(errorText(e)); }
  }

  return (
    <div className="tag-budget">
      <span>بودجه (ساعت)</span>
      <input type="number" min={0} step={0.5} inputMode="decimal" placeholder="بدون بودجه" aria-label={`بودجه‌ی ساعت تگ ${tag.name}`} value={hours}
        onChange={(e) => setHours(e.target.value)} onKeyDown={(e) => e.key === "Enter" && save()} />
      <select aria-label="شمارش از" value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: "auto" }}>
        <option value="all">کل سابقه‌ی تگ</option>
        <option value="today">از امروز</option>
      </select>
      <button className="btn btn-outline btn-sm" onClick={save}>ثبت بودجه</button>
      <span className="tag-budget-msg">{msg}</span>
      {tag.budget_minutes ? (
        <div className="tag-budget-progress">
          <BudgetBar percent={tag.budget_percent} />
          <div className="budget-text">{budgetText(tag, fmtHM)}</div>
        </div>
      ) : null}
    </div>
  );
}

function CompanyEditor({ tag, catalog, onSaved, toast }: { tag: Tag; catalog?: Catalog; onSaved: () => Promise<void>; toast: (m: string) => void }) {
  const [type, setType] = useState<number | null>(tag.report_type_id);
  const [story, setStory] = useState<number | null>(tag.story_id);
  const [weight, setWeight] = useState(tag.fill_weight === null ? "" : String(tag.fill_weight));
  const [msg, setMsg] = useState("");
  const projectOf = catalog?.projects.find((p) => p.stories.some((s) => s.id === story))?.name;

  async function save() {
    setMsg("");
    try {
      await put(`/api/tags/${tag.id}/company`, { report_type_id: type, story_id: story, fill_weight: weight.trim() === "" ? null : Number(weight) });
      toast(`فیلدهای سامانه‌ی «${tag.name}» ثبت شد`);
      await onSaved();
    } catch (e) { setMsg(errorText(e)); }
  }

  return (
    <div className="tag-company">
      <label>
        <span>نوع گزارش</span>
        <select aria-label="نوع گزارش" value={type ?? ""} onChange={(e) => setType(e.target.value ? Number(e.target.value) : null)}>
          <option value="">—</option>
          {catalog?.types.filter((t) => t.id).map((t) => <option key={t.id} value={t.id!}>{t.name}</option>)}
        </select>
      </label>
      <label style={{ flex: "2 1 260px" }}>
        <span>استوری{projectOf ? ` · پروژه: ${projectOf}` : ""}</span>
        <StoryPicker catalog={catalog} value={story} onChange={(id) => setStory(id)} />
      </label>
      <label style={{ flex: "0 0 90px", minWidth: 90 }} title="سهم این تگ از پر کردن فاصله‌ی حضور: ۱ معمولی، ۲ دو برابر، ۰ هیچ‌وقت">
        <span>وزن پر کردن</span>
        <input type="number" min={0} max={10} step={0.5} placeholder="۱" value={weight} onChange={(e) => setWeight(e.target.value)} />
      </label>
      <button className="btn btn-outline btn-sm" onClick={save}>ثبت سامانه</button>
      <span className="tag-budget-msg">{msg}</span>
    </div>
  );
}
