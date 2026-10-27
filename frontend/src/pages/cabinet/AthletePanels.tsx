import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorText, json } from "../../shared/api";
import { formatDate, keys, linkStatusLabels, rankLabels, requestKindLabels, requestStatusLabels } from "../../shared/labels";
import type { CoachLink, HistoryItem, MyRank, RequestKind, SportRank } from "../../shared/types";
import { FormError, Notice } from "../../shared/ui";
import { ValidityBadge } from "../../shared/widgets";

export function MyCoaches() {
  const [links, setLinks] = useState<CoachLink[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<CoachLink[]>("/me/coach-links").then(setLinks).catch((reason) => setError(errorText(reason))); }, []);
  useEffect(load, [load]);

  async function respond(link: CoachLink, accept: boolean) {
    setError(null);
    try { await api(`/me/coach-links/${link.id}/respond`, json("POST", { accept })); load(); } catch (reason) { setError(errorText(reason)); }
  }

  const visible = links?.filter((link) => link.status !== "declined") ?? [];
  return (
    <section className="card">
      <h2>Мои тренеры</h2>
      {links && visible.length === 0 && <p className="muted">Тренер находит вас в реестре и отправляет запрос — он появится здесь для подтверждения.</p>}
      <ul className="ref-list">
        {visible.map((link) => (
          <li key={link.id}>
            <span>{link.coach_name}<br /><small className="muted">{link.discipline.name} · с {formatDate(link.created_at)}</small></span>
            <span className="row-actions">
              {link.status === "pending" ? <>
                <button type="button" className="button button--small" onClick={() => void respond(link, true)}>Подтвердить</button>
                <button type="button" className="link-button" onClick={() => void respond(link, false)}>Отклонить</button>
              </> : <span className={`app-status app-status--${link.status === "active" ? "approved" : "withdrawn"}`}>{linkStatusLabels[link.status]}</span>}
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} />
    </section>
  );
}

/** Форма заявки на разряд: результат из опубликованного протокола — основание. */
export function RankRequestForm({ results, athleteId, currentRank, onDone }: { results: HistoryItem[]; athleteId?: number; currentRank?: SportRank | null; onDone: () => void }) {
  const eligible = results.filter((item) => item.result_status === "ok");
  const [form, setForm] = useState<{ rank: SportRank; kind: RequestKind; application_id: number | "" }>({ rank: currentRank ?? "third", kind: "assign", application_id: eligible[0]?.application_id ?? "" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (eligible.length === 0) return <p className="muted">Заявку на разряд можно подать после публикации протокола соревнования с результатом.</p>;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try {
      await api("/rank-requests", json("POST", { ...form, athlete_id: athleteId }));
      setNotice("Заявка отправлена в федерацию");
      onDone();
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <form className="form-grid" onSubmit={submit}>
      <label>Разряд<select value={form.rank} onChange={(event) => setForm({ ...form, rank: event.target.value as SportRank })}>{keys(rankLabels).map((item) => <option key={item} value={item}>{rankLabels[item]}</option>)}</select></label>
      <label>Тип заявки<select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as RequestKind })}>{keys(requestKindLabels).map((item) => <option key={item} value={item}>{requestKindLabels[item]}</option>)}</select></label>
      <label className="form-wide">Основание — результат
        <select value={form.application_id} onChange={(event) => setForm({ ...form, application_id: Number(event.target.value) })}>
          {eligible.map((item) => <option key={item.application_id} value={item.application_id}>{item.competition.title} — {item.place ? `${item.place} место` : "без места"}, {formatDate(item.competition.date)}</option>)}
        </select>
      </label>
      <FormError error={error} /><Notice text={notice} />
      <button className="button form-wide">Подать заявку на разряд</button>
    </form>
  );
}

export function MyRankCard() {
  const [data, setData] = useState<MyRank | null>(null);
  const [results, setResults] = useState<HistoryItem[]>([]);
  const load = useCallback(() => {
    api<MyRank>("/me/rank").then(setData).catch(() => setData(null));
    api<HistoryItem[]>("/me/results").then(setResults).catch(() => setResults([]));
  }, []);
  useEffect(load, [load]);
  if (!data) return null;
  const pending = data.requests.some((item) => item.status === "pending");

  return (
    <section className="card">
      <h2>Разряд</h2>
      {data.current ? (
        <p><strong>{rankLabels[data.current.rank]}</strong> <ValidityBadge validity={data.current.validity} until={data.current.expires_on} /><br />
          <small className="muted">Присвоен {formatDate(data.current.assigned_on)}, {data.current.order_ref}</small></p>
      ) : <p className="muted">Разряд пока не присвоен.</p>}
      {data.current?.validity === "expiring" && <p className="form-warning">Срок разряда скоро истекает — подайте заявку на подтверждение.</p>}
      {data.current?.validity === "expired" && <p className="form-error">Срок разряда истёк.</p>}
      {data.requests.length > 0 && (
        <ul className="ref-list">
          {data.requests.map((item) => (
            <li key={item.id}>
              <span>{requestKindLabels[item.kind]}: {rankLabels[item.rank]}<br /><small className="muted">«{item.basis.competition.title}», {item.basis.place ?? "—"} место · подал {item.submitted_by}</small>
                {item.moderator_comment && <><br /><small className="muted">Комментарий: {item.moderator_comment}</small></>}</span>
              <span className={`app-status app-status--${item.status === "pending" ? "pending" : item.status}`}>{requestStatusLabels[item.status]}</span>
            </li>
          ))}
        </ul>
      )}
      {data.has_coach ? <p className="muted">Заявку на разряд подаёт ваш тренер.</p> : !pending && <RankRequestForm results={results} currentRank={data.current?.rank} onDone={load} />}
    </section>
  );
}
