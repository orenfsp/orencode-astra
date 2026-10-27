import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, json } from "../../shared/api";
import { categoryLabels, formatDate, keys, requestKindLabels, requestStatusLabels, todayIso } from "../../shared/labels";
import type { JudgeCategory, MyJudge, RequestKind } from "../../shared/types";
import { FormError, Notice } from "../../shared/ui";
import { ValidityBadge } from "../../shared/widgets";

export function JudgePanel() {
  const [data, setData] = useState<MyJudge | null>(null);
  const [form, setForm] = useState<{ category: JudgeCategory; kind: RequestKind; justification: string }>({ category: "third", kind: "assign", justification: "" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const load = useCallback(() => { api<MyJudge>("/me/judge").then(setData).catch((reason) => setError(errorText(reason))); }, []);
  useEffect(load, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try { await api("/me/judge/requests", json("POST", form)); setNotice("Заявка отправлена в федерацию"); setForm({ ...form, justification: "" }); load(); } catch (reason) { setError(errorText(reason)); }
  }

  if (!data) return <FormError error={error} />;
  const today = todayIso();
  const upcoming = data.assignments.filter((item) => item.competition.end_date >= today);
  const past = data.assignments.filter((item) => item.competition.end_date < today);
  const pending = data.requests.some((item) => item.status === "pending");

  return (
    <>
      <section className="card">
        <h2>Судейская категория</h2>
        {data.info.category ? (
          <p><strong>{categoryLabels[data.info.category]}</strong> <ValidityBadge validity={data.info.validity} until={data.info.category_expires_on} /><br />
            <small className="muted">Присвоена {formatDate(data.info.category_assigned_on)}, {data.info.order_ref}</small></p>
        ) : <p className="muted">Категория пока не присвоена.</p>}
        {data.info.validity === "expiring" && <p className="form-warning">Срок категории скоро истекает — подайте заявку на подтверждение.</p>}
        {data.requests.length > 0 && (
          <ul className="ref-list">
            {data.requests.map((item) => (
              <li key={item.id}>
                <span>{requestKindLabels[item.kind]}: {categoryLabels[item.category]}<br /><small className="muted">{formatDate(item.created_at)}{item.moderator_comment ? ` · ${item.moderator_comment}` : ""}</small></span>
                <span className={`app-status app-status--${item.status}`}>{requestStatusLabels[item.status]}</span>
              </li>
            ))}
          </ul>
        )}
        {!pending && (
          <form className="form-grid" onSubmit={submit}>
            <label>Категория<select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value as JudgeCategory })}>{keys(categoryLabels).map((item) => <option key={item} value={item}>{categoryLabels[item]}</option>)}</select></label>
            <label>Тип заявки<select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as RequestKind })}>{keys(requestKindLabels).map((item) => <option key={item} value={item}>{requestKindLabels[item]}</option>)}</select></label>
            <label className="form-wide">Обоснование<textarea required minLength={10} maxLength={4000} rows={3} placeholder="Какие соревнования судили, в какой должности" value={form.justification} onChange={(event) => setForm({ ...form, justification: event.target.value })} /></label>
            <button className="button form-wide">Подать заявку на категорию</button>
          </form>
        )}
        <FormError error={error} /><Notice text={notice} />
      </section>
      <section className="card">
        <h2>Назначения</h2>
        {upcoming.length === 0 && <p className="muted">Предстоящих назначений нет.</p>}
        <ul className="ref-list">{upcoming.map((item) => <li key={item.id}><span>{item.competition.title}<br /><small className="muted">{formatDate(item.competition.date)}</small></span><span className="tag">{item.position.name}</span></li>)}</ul>
      </section>
      <section className="card">
        <h2>Мои соревнования</h2>
        {past.length === 0 && <p className="muted">Здесь появятся соревнования, на которых вы работали.</p>}
        <ul className="ref-list">{past.map((item) => <li key={item.id}><span>{item.competition.title}<br /><small className="muted">{formatDate(item.competition.date)}</small></span><span className="tag">{item.position.name}</span></li>)}</ul>
      </section>
    </>
  );
}
