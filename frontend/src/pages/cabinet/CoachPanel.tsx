import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorText, json } from "../../shared/api";
import { applicationStatusLabels, birthYear, formatDate, linkStatusLabels, rankLabels, requestStatusLabels } from "../../shared/labels";
import type { Application, AthleteSearchResult, CoachAthleteSummary, CoachLink, RankRequest } from "../../shared/types";
import { FormError, Notice } from "../../shared/ui";
import { RankRequestForm } from "./AthletePanels";

function FindAthlete({ onLinked }: { onLinked: () => void }) {
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<AthleteSearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function search(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try { setFound(await api<AthleteSearchResult[]>(`/coach/athletes/search?q=${encodeURIComponent(query)}`)); } catch (reason) { setError(errorText(reason)); }
  }

  async function link(athlete: AthleteSearchResult, disciplineId: number) {
    setError(null); setNotice(null);
    try {
      await api("/coach/links", json("POST", { athlete_id: athlete.id, discipline_id: disciplineId }));
      setNotice(`Запрос отправлен: ${athlete.full_name}. Спортсмен подтвердит его в своём кабинете.`);
      onLinked();
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card">
      <h2>Найти спортсмена в реестре</h2>
      <form className="inline-form" onSubmit={search}>
        <input required minLength={2} placeholder="Фамилия или имя" value={query} onChange={(event) => setQuery(event.target.value)} />
        <button className="button button--small">Найти</button>
      </form>
      {found?.length === 0 && <p className="muted">Никого не нашли. Спортсмен должен быть зарегистрирован и заполнить раздел «Спортсмен».</p>}
      <ul className="ref-list">
        {found?.map((athlete) => (
          <li key={athlete.id}>
            <span>{athlete.full_name}<br /><small className="muted">{birthYear(athlete.birth_date)} г. р. · {athlete.organization ?? "без организации"}</small></span>
            <span className="row-actions">
              {athlete.disciplines.map((discipline) => (
                <button key={discipline.id} type="button" className="button button--small button--ghost" onClick={() => void link(athlete, discipline.id)} title="Отправить запрос на привязку">
                  + {discipline.name.replace("Программирование ", "")}
                </button>
              ))}
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

function Links({ links, reload }: { links: CoachLink[]; reload: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function change(link: CoachLink, status: "active" | "suspended" | "ended") {
    if (status === "ended" && !window.confirm(`Завершить связь со спортсменом ${link.athlete.full_name}?`)) return;
    setError(null);
    try { await api(`/coach/links/${link.id}/status`, json("POST", { status })); reload(); } catch (reason) { setError(errorText(reason)); }
  }
  return (
    <section className="card">
      <h2>Мои спортсмены</h2>
      {links.length === 0 && <p className="muted">Пока никого. Найдите спортсмена в реестре и отправьте запрос на привязку.</p>}
      <ul className="ref-list">
        {links.map((link) => (
          <li key={link.id}>
            <details>
              <summary>{link.athlete.full_name} · <span className="muted">{link.discipline.name}</span></summary>
              <ol className="history-list">
                {link.history.map((event) => <li key={event.created_at + event.status}>{formatDate(event.created_at)} — {linkStatusLabels[event.status]}{event.changed_by ? `, ${event.changed_by}` : ""}{event.note ? ` (${event.note})` : ""}</li>)}
              </ol>
            </details>
            <span className="row-actions">
              <span className={`app-status app-status--${link.status === "active" ? "approved" : link.status === "pending" ? "pending" : "withdrawn"}`}>{linkStatusLabels[link.status]}</span>
              {link.status === "active" && <button type="button" className="link-button" onClick={() => void change(link, "suspended")}>Приостановить</button>}
              {link.status === "suspended" && <button type="button" className="link-button" onClick={() => void change(link, "active")}>Возобновить</button>}
              {["active", "suspended", "pending"].includes(link.status) && <button type="button" className="link-button danger" onClick={() => void change(link, "ended")}>Завершить</button>}
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} />
    </section>
  );
}

function Athletes({ summary, requests, reload }: { summary: CoachAthleteSummary[]; requests: RankRequest[]; reload: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  if (summary.length === 0) return null;
  return (
    <section className="card">
      <h2>Разряды и результаты подопечных</h2>
      <ul className="ref-list">
        {summary.map((item) => {
          const pending = requests.find((request) => request.athlete.id === item.athlete.id && request.status === "pending");
          return (
            <li key={item.athlete.id} className="stacked">
              <div className="row-split">
                <span><strong>{item.athlete.full_name}</strong><br /><small className="muted">{item.rank ? `${rankLabels[item.rank.rank]} до ${formatDate(item.rank.expires_on)}` : "без разряда"} · выступлений: {item.results.length}</small></span>
                <span className="row-actions">
                  {pending ? <span className="app-status app-status--pending">Заявка на разряд: {requestStatusLabels.pending}</span>
                    : <button type="button" className="link-button" onClick={() => setOpen(open === item.athlete.id ? null : item.athlete.id)}>{open === item.athlete.id ? "Свернуть" : "Заявка на разряд"}</button>}
                </span>
              </div>
              {item.results.length > 0 && (
                <ul className="mini-results">
                  {item.results.map((result) => <li key={result.application_id}>{formatDate(result.competition.date)} · {result.competition.title} — {result.place ? `${result.place} из ${result.participants}` : "без места"}</li>)}
                </ul>
              )}
              {open === item.athlete.id && <RankRequestForm results={item.results} athleteId={item.athlete.id} currentRank={item.rank?.rank} onDone={() => { setOpen(null); reload(); }} />}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Applications({ items }: { items: Application[] }) {
  return (
    <section className="card">
      <h2>Заявки на соревнования</h2>
      {items.length === 0 && <p className="muted">Откройте соревнование в <Link to="/">календаре</Link> — там можно подать заявку за каждого привязанного спортсмена.</p>}
      <ul className="ref-list">
        {items.map((item) => (
          <li key={item.id}>
            <span>{item.athlete.full_name} — <Link to={`/competitions/${item.competition.id}`}>{item.competition.title}</Link><br /><small className="muted">{formatDate(item.competition.date)} · {item.age_group.name}</small></span>
            <span className={`app-status app-status--${item.status}`}>{applicationStatusLabels[item.status]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CoachPanel() {
  const [links, setLinks] = useState<CoachLink[]>([]);
  const [summary, setSummary] = useState<CoachAthleteSummary[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [requests, setRequests] = useState<RankRequest[]>([]);
  const load = useCallback(() => {
    api<CoachLink[]>("/coach/links").then(setLinks).catch(() => setLinks([]));
    api<CoachAthleteSummary[]>("/coach/athletes").then(setSummary).catch(() => setSummary([]));
    api<Application[]>("/coach/applications").then(setApplications).catch(() => setApplications([]));
    api<RankRequest[]>("/coach/rank-requests").then(setRequests).catch(() => setRequests([]));
  }, []);
  useEffect(load, [load]);
  return (
    <>
      <Links links={links} reload={load} />
      <Athletes summary={summary} requests={requests} reload={load} />
      <Applications items={applications} />
      <FindAthlete onLinked={load} />
    </>
  );
}
