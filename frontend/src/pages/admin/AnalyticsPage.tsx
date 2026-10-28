import { Fragment, useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../../app/session";
import { api, errorText, fileUrl, json } from "../../shared/api";
import { changeText, formatDate, levelLabels, organizationTypeLabels, planLabels } from "../../shared/labels";
import type { Development, Effectiveness, EffectivenessLine } from "../../shared/types";
import { FormError, Notice, PageTitle, State } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

const YEAR = new Date().getFullYear();
const SEASONS = [YEAR - 2, YEAR - 1, YEAR];

function SeasonPicker({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <div className="chip-filter" role="group" aria-label="Год">
      {SEASONS.map((item) => <button key={item} type="button" className={`role-chip${item === value ? " is-active" : ""}`} onClick={() => onChange(item)}>{item}</button>)}
    </div>
  );
}

function Documents({ data, indicator, editable, reload }: { data: Development; indicator: string; editable: boolean; reload: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const item = data.indicators.find((entry) => entry.key === indicator);
  if (!item) return null;

  async function upload(file: File | undefined) {
    if (!file) return;
    const body = new FormData();
    body.append("indicator", indicator);
    body.append("year", String(data.year));
    body.append("file", file);
    setError(null);
    try { await api("/development/documents", { method: "POST", body }); reload(); } catch (reason) { setError(errorText(reason)); }
  }
  async function remove(id: number) {
    try { await api(`/development/documents/${id}`, { method: "DELETE" }); reload(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <div className="indicator-meta">
      <small className="muted">Источник данных: {item.source}</small>
      <div className="row-actions start">
        {item.documents.map((document) => (
          <span key={document.id} className="tag">
            <a href={fileUrl(`/development/documents/${document.id}`)}>{document.filename}</a>
            {editable && <button type="button" className="link-button danger" aria-label={`Удалить ${document.filename}`} onClick={() => void remove(document.id)}> ×</button>}
          </span>
        ))}
        {editable && <label className="file-button">+ Подтверждающий документ<input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" onChange={(event) => void upload(event.target.files?.[0])} /></label>}
        {!editable && item.documents.length === 0 && <small className="muted">документы не приложены</small>}
      </div>
      <FormError error={error} />
    </div>
  );
}

export function DevelopmentView() {
  const { user } = useSession();
  const [year, setYear] = useState(YEAR);
  const [data, setData] = useState<Development | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<Development>(`/development?year=${year}`).then(setData).catch((reason) => setError(errorText(reason))); }, [year]);
  useEffect(load, [load]);
  const editable = user?.active_role === "federation_admin";

  if (error) return <State code="ERR" title="Показатели не загрузились" text={error} />;
  return (
    <>
      <SeasonPicker value={year} onChange={setYear} />
      {!data ? <State code="…" title="Собираем показатели" text="Подождите секунду." /> : (
        <div className="ref-grid">
          <section className="card">
            <h2>Численность занимающихся</h2>
            <div className="stat-grid compact">
              {data.headcount_years.map((item, index) => <div key={item} className="stat"><strong>{data.headcount[index]}</strong><span>{item}</span></div>)}
              <div className="stat"><strong>{changeText(data.headcount)}</strong><span>к прошлому году</span></div>
            </div>
            <Documents data={data} indicator="headcount" editable={editable} reload={load} />
          </section>
          <section className="card">
            <h2>Организации, ведущие подготовку · {data.organizations.length}</h2>
            <ul className="ref-list">
              {data.organizations.map((item) => <li key={item.name}><span>{item.name}<br /><small className="muted">{organizationTypeLabels[item.org_type]}{item.municipality ? ` · ${item.municipality}` : ""} · {item.disciplines.length} дисц.</small></span><span className="counter-badge">{item.athletes}</span></li>)}
            </ul>
            <Documents data={data} indicator="organizations" editable={editable} reload={load} />
          </section>
          <section className="card card--wide">
            <h2>Официальные соревнования в {data.year} году · {data.competitions.length}, в календарных планах — {data.competitions_in_plans}</h2>
            <div className="table-wrap">
              <table className="protocol-table">
                <thead><tr><th>Дата</th><th>Соревнование</th><th>Статус</th><th>Календарный план</th><th>Участников</th><th>Протокол</th></tr></thead>
                <tbody>
                  {data.competitions.map((item) => (
                    <tr key={item.id}>
                      <td className="nowrap">{formatDate(item.date)}</td>
                      <td>{item.title}<br /><small className="muted">{item.discipline}</small></td>
                      <td>{levelLabels[item.level]}</td>
                      <td>{planLabels[item.calendar_plan]}{item.calendar_plan_number ? `, № ${item.calendar_plan_number}` : ""}</td>
                      <td>{item.participants}</td>
                      <td>{item.protocol_published ? <Link to={`/competitions/${item.id}/protocol`}>открыть</Link> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Documents data={data} indicator="competitions" editable={editable} reload={load} />
          </section>
        </div>
      )}
    </>
  );
}

function EffectivenessTable({ title, lines }: { title: string; lines: EffectivenessLine[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section className="card card--wide">
      <h2>{title}</h2>
      {lines.length === 0 && <p className="muted">Нет результатов в опубликованных протоколах за сезон.</p>}
      {lines.length > 0 && (
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>№</th><th>Название</th><th>Спортсменов</th><th>Стартов</th><th>Призовых</th><th>Побед</th><th>Баллы</th><th>На спортсмена</th><th>Разрядов</th><th /></tr></thead>
            <tbody>
              {lines.map((line, index) => (
                <Fragment key={line.name}>
                  <tr>
                    <td className="place">{index + 1}</td><td>{line.name}</td><td>{line.athletes}</td><td>{line.starts}</td><td>{line.podiums}</td>
                    <td>{line.wins}</td><td className="place">{line.points}</td><td>{line.points_per_athlete}</td><td>{line.ranks}</td>
                    <td><button type="button" className="link-button" onClick={() => setOpen(open === line.name ? null : line.name)}>{open === line.name ? "Скрыть" : "Откуда"}</button></td>
                  </tr>
                  {open === line.name && (
                    <tr className="rating-detail"><td colSpan={10}>
                      <ul className="mini-results">{line.details.map((detail, position) => <li key={position}>{formatDate(detail.date)} · {detail.athlete} — {detail.competition}: {detail.place ? `${detail.place} место` : "без места"} → {detail.points} б.</li>)}</ul>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function EffectivenessView() {
  const [season, setSeason] = useState(YEAR);
  const [data, setData] = useState<Effectiveness | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setData(null); api<Effectiveness>(`/analytics/effectiveness?season=${season}`).then(setData).catch((reason) => setError(errorText(reason))); }, [season]);
  if (error) return <State code="ERR" title="Не удалось посчитать" text={error} />;
  return (
    <>
      <div className="inline-form"><SeasonPicker value={season} onChange={setSeason} /><a className="button button--small" href={fileUrl(`/analytics/effectiveness.xlsx?season=${season}`)}>Скачать .xlsx</a></div>
      {!data ? <State code="…" title="Считаем" text="Сводим результаты подопечных." /> : (
        <div className="ref-grid">
          <EffectivenessTable title="Тренеры" lines={data.coaches} />
          <EffectivenessTable title="Организации" lines={data.organizations} />
          <p className="muted card--wide">{data.method}</p>
        </div>
      )}
    </>
  );
}

function MinistryAccess() {
  const [users, setUsers] = useState<{ id: number; email: string; name: string }[]>([]);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const load = useCallback(() => { api<typeof users>("/admin/ministry-access").then(setUsers).catch(() => setUsers([])); }, []);
  useEffect(load, [load]);
  async function grant(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try { const user = await api<{ name: string }>("/admin/ministry-access", json("POST", { email })); setNotice(`Доступ выдан: ${user.name}`); setEmail(""); load(); } catch (reason) { setError(errorText(reason)); }
  }
  return (
    <section className="card">
      <h2>Доступ министерства</h2>
      <p className="muted">Только чтение: показатели, численность, календарь, составы сборной, эффективность. Сотрудник регистрируется сам, затем федерация выдаёт доступ.</p>
      <ul className="ref-list">{users.map((user) => <li key={user.id}><span>{user.name}</span><span className="muted">{user.email}</span></li>)}</ul>
      <form className="inline-form" onSubmit={grant}>
        <input type="email" required placeholder="email сотрудника министерства" value={email} onChange={(event) => setEmail(event.target.value)} />
        <button className="button button--small">Выдать доступ</button>
      </form>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

export function AnalyticsPage() {
  const [tab, setTab] = useState<"development" | "effectiveness">("development");
  const { user } = useSession();
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Аналитика">
        <p className="lead">Показатели развития вида спорта в регионе и эффективность тренеров и организаций — по данным платформы.</p>
      </PageTitle>
      <AdminGate roles={["federation_admin", "ministry"]}>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "development"} className={tab === "development" ? "is-active" : ""} onClick={() => setTab("development")}>Показатели развития</button>
          <button type="button" role="tab" aria-selected={tab === "effectiveness"} className={tab === "effectiveness" ? "is-active" : ""} onClick={() => setTab("effectiveness")}>Эффективность тренеров и организаций</button>
        </div>
        {tab === "development" ? <DevelopmentView /> : <EffectivenessView />}
        {user?.active_role === "federation_admin" && tab === "development" && <div className="ref-grid spaced"><MinistryAccess /></div>}
      </AdminGate>
    </section>
  );
}
