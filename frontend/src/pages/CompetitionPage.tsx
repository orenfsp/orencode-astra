import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useSession } from "../app/session";
import { API_BASE, api, errorText, json } from "../shared/api";
import { applicationStatusLabels, formatDate, formatLabels, formatRange, levelLabels, planLabels } from "../shared/labels";
import type { Application, CoachLink, Competition, Eligibility } from "../shared/types";
import { FormError, Notice, State, StatusBadge } from "../shared/ui";

type CoachRow = { link: CoachLink; eligibility: Eligibility };

/** Тренер видит своих спортсменов по дисциплине соревнования и подаёт заявку за каждого. */
function CoachApplyBlock({ competition }: { competition: Competition }) {
  const [rows, setRows] = useState<CoachRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const links = (await api<CoachLink[]>("/coach/links")).filter((link) => link.status === "active" && link.discipline.id === competition.discipline.id);
    setRows(await Promise.all(links.map(async (link) => ({ link, eligibility: await api<Eligibility>(`/competitions/${competition.id}/eligibility?athlete_id=${link.athlete.id}`) }))));
  }, [competition.id, competition.discipline.id]);
  useEffect(() => { load().catch((reason) => setError(errorText(reason))); }, [load]);

  async function apply(row: CoachRow) {
    setError(null); setNotice(null);
    try {
      await api(`/competitions/${competition.id}/applications`, json("POST", { athlete_id: row.link.athlete.id }));
      setNotice(`Заявка за ${row.link.athlete.full_name} отправлена на модерацию`);
      await load();
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card apply-card">
      <h2>Заявки за спортсменов</h2>
      <p className="muted">Приём заявок до {formatDate(competition.registration_end)}</p>
      {rows?.length === 0 && <p className="muted">Нет спортсменов с активной связью по дисциплине «{competition.discipline.name}». <Link to="/cabinet">Мои спортсмены</Link></p>}
      <ul className="ref-list">
        {rows?.map((row) => (
          <li key={row.link.id}>
            <span>{row.link.athlete.full_name}<br />
              <small className="muted">{row.eligibility.eligible ? `Группа: ${row.eligibility.age_group?.name}` : row.eligibility.reasons.join("; ")}</small></span>
            <span className="row-actions">
              {row.eligibility.application_status && row.eligibility.application_status !== "withdrawn"
                ? <span className={`app-status app-status--${row.eligibility.application_status}`}>{applicationStatusLabels[row.eligibility.application_status]}</span>
                : row.eligibility.eligible && <button type="button" className="button button--small" onClick={() => void apply(row)}>Подать заявку</button>}
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

function ApplicationBlock({ competition }: { competition: Competition }) {
  const { user } = useSession();
  if (user?.active_role === "coach" && competition.status === "registration_open") return <CoachApplyBlock competition={competition} />;
  return <AthleteApplyBlock competition={competition} />;
}

function AthleteApplyBlock({ competition }: { competition: Competition }) {
  const { user } = useSession();
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<Eligibility>(`/competitions/${competition.id}/eligibility`).then(setEligibility).catch((reason) => setError(errorText(reason)));
  }, [competition.id]);

  useEffect(() => { if (user) load(); }, [user, load]);

  if (competition.status !== "registration_open") return null;
  if (user === null) {
    return (
      <section className="card apply-card">
        <h2>Заявка на участие</h2>
        <p className="muted">Приём заявок до {formatDate(competition.registration_end)} — войдите как спортсмен, чтобы подать заявку.</p>
        <Link className="button" to="/login">Войти</Link>
      </section>
    );
  }
  if (!user || !eligibility) return null;

  async function apply() {
    setBusy(true); setError(null); setNotice(null);
    try {
      await api<Application>(`/competitions/${competition.id}/applications`, { method: "POST" });
      setNotice("Заявка отправлена в федерацию на модерацию");
      load();
    } catch (reason) { setError(errorText(reason)); }
    finally { setBusy(false); }
  }

  const status = eligibility.application_status;
  return (
    <section className="card apply-card">
      <h2>Заявка на участие</h2>
      <p className="muted">Приём заявок до {formatDate(competition.registration_end)}</p>
      {status && status !== "withdrawn" && (
        <p><span className={`app-status app-status--${status}`}>{applicationStatusLabels[status]}</span> <Link to="/cabinet">Мои заявки</Link></p>
      )}
      {eligibility.eligible ? (
        <>
          <p>Вы проходите в группу <strong>{eligibility.age_group?.name}</strong> (в {competition.date.slice(0, 4)} году вам {eligibility.age}).</p>
          <button type="button" className="button" disabled={busy} onClick={() => void apply()}>{busy ? "Отправляем…" : "Подать заявку"}</button>
        </>
      ) : (
        <ul className="reason-list">{eligibility.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
      )}
      {!eligibility.eligible && user.active_role === "athlete" && eligibility.reasons.some((reason) => reason.includes("профил")) && (
        <Link className="button button--ghost button--small" to="/cabinet">Заполнить профиль</Link>
      )}
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

export function CompetitionPage() {
  const { id } = useParams();
  const { user } = useSession();
  const [item, setItem] = useState<Competition | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Competition>(`/competitions/${id}`).then(setItem).catch((reason) => setError(errorText(reason)));
  }, [id, user?.active_role]);

  return (
    <section className="section detail">
      <Link className="back-link" to="/">← К календарю</Link>
      {!item && !error && <State code="…" title="Загружаем соревнование" text="Получаем актуальные данные." />}
      {error && <State code="404" title="Соревнование не найдено" text={error} />}
      {item && (
        <article>
          <div className="event-tags">
            <StatusBadge status={item.status} />
            <span className="tag">{levelLabels[item.level]}</span>
            <span className="tag">{item.competition_type.name}</span>
          </div>
          <h1 className="detail-title">{item.title}</h1>
          <p className="event-discipline">{item.discipline.name}</p>
          <p className="detail-text">{item.description}</p>
          <dl className="detail-grid">
            <div><dt>Даты проведения</dt><dd>{formatRange(item.date, item.end_date)}</dd></div>
            <div><dt>Место</dt><dd>{item.location}</dd></div>
            <div><dt>Формат</dt><dd>{formatLabels[item.format]}</dd></div>
            <div><dt>Возрастные группы</dt><dd>{item.age_groups.map((group) => group.name).join("; ")}</dd></div>
            <div><dt>Приём заявок</dt><dd>{formatDate(item.registration_start)} — {formatDate(item.registration_end)}</dd></div>
            <div><dt>Календарный план</dt><dd>{planLabels[item.calendar_plan]}{item.calendar_plan_number ? `, № ${item.calendar_plan_number}` : ""}</dd></div>
          </dl>
          <div className="detail-actions">
            {item.regulation_filename
              ? <a className="button button--ghost" href={`${API_BASE}/api/v1/competitions/${item.id}/regulation`}>Скачать положение</a>
              : <span className="muted">Положение будет опубликовано позже</span>}
            {item.protocol_published_at && <Link className="button" to={`/competitions/${item.id}/protocol`}>Протокол</Link>}
            {user?.active_role === "federation_admin" && <Link className="link-button" to={`/admin/competitions/${item.id}`}>Заявки и результаты →</Link>}
          </div>
          <ApplicationBlock competition={item} />
        </article>
      )}
    </section>
  );
}
