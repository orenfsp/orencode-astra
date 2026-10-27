import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorText, json } from "./api";
import { addYears, daysLeftText, formatDate, todayIso, validityLabels } from "./labels";
import type { Deadline, Validity } from "./types";
import { FormError } from "./ui";

export function ValidityBadge({ validity, until }: { validity: Validity; until?: string | null }) {
  if (validity === "none") return <span className="app-status app-status--withdrawn">нет</span>;
  const tone = validity === "valid" ? "approved" : validity === "expiring" ? "pending" : "rejected";
  return <span className={`app-status app-status--${tone}`}>{validityLabels[validity]}{until ? ` · до ${formatDate(until)}` : ""}</span>;
}

/** Сроки активной роли: приём заявок, разряды, категории, ходатайства. */
export function DeadlinesCard({ role }: { role: string }) {
  const [items, setItems] = useState<Deadline[] | null>(null);
  useEffect(() => { api<Deadline[]>("/me/deadlines").then(setItems).catch(() => setItems([])); }, [role]);
  return (
    <section className="card">
      <h2>Сроки</h2>
      {items?.length === 0 && <p className="muted">Ближайших сроков нет.</p>}
      <ul className="deadline-list">
        {items?.map((item) => (
          <li key={`${item.kind}-${item.title}-${item.date}`} className={`deadline deadline--${item.severity}`}>
            <span className="deadline-date"><strong>{formatDate(item.date)}</strong><small>{daysLeftText(item.days_left)}</small></span>
            {item.link ? <Link to={item.link}>{item.title}</Link> : <span>{item.title}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Решение федерации по заявке на разряд или категорию: одобрить с датой, приказом и сроком или отклонить с причиной.
 */
export function DecisionForm({ path, defaultYears, onDone }: { path: string; defaultYears: number; onDone: () => void }) {
  const today = todayIso();
  const [mode, setMode] = useState<"approved" | "rejected">("approved");
  const [form, setForm] = useState({ assigned_on: today, expires_on: addYears(today, defaultYears), order_ref: "", comment: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null);
    const body = mode === "approved" ? { status: mode, assigned_on: form.assigned_on, expires_on: form.expires_on, order_ref: form.order_ref } : { status: mode, comment: form.comment };
    try { await api(path, json("POST", body)); onDone(); } catch (reason) { setError(errorText(reason)); } finally { setBusy(false); }
  }

  return (
    <form className="decision" onSubmit={submit}>
      <div className="chip-filter">
        <button type="button" className={`role-chip${mode === "approved" ? " is-active" : ""}`} onClick={() => setMode("approved")}>Присвоить</button>
        <button type="button" className={`role-chip${mode === "rejected" ? " is-active" : ""}`} onClick={() => setMode("rejected")}>Отказать</button>
      </div>
      {mode === "approved" ? (
        <div className="decision-fields">
          <label>Дата присвоения<input type="date" required value={form.assigned_on} onChange={(event) => setForm({ ...form, assigned_on: event.target.value, expires_on: addYears(event.target.value, defaultYears) })} /></label>
          <label>Действует до<input type="date" required min={form.assigned_on} value={form.expires_on} onChange={(event) => setForm({ ...form, expires_on: event.target.value })} /></label>
          <label>Приказ<input required maxLength={120} placeholder="№ и дата приказа" value={form.order_ref} onChange={(event) => setForm({ ...form, order_ref: event.target.value })} /></label>
        </div>
      ) : (
        <label>Причина отказа<input required maxLength={1000} value={form.comment} onChange={(event) => setForm({ ...form, comment: event.target.value })} /></label>
      )}
      <FormError error={error} />
      <button className="button button--small" disabled={busy}>{mode === "approved" ? "Зафиксировать" : "Отказать"}</button>
    </form>
  );
}
