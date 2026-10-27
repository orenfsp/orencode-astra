import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../../shared/api";
import { daysLeftText, formatDate } from "../../shared/labels";
import type { Dashboard } from "../../shared/types";
import { PageTitle, State, StatusBadge } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

function DashboardView() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Dashboard>("/admin/dashboard").then(setData).catch((reason) => setError(errorText(reason))); }, []);
  if (error) return <State code="ERR" title="Дашборд не загрузился" text={error} />;
  if (!data) return <State code="…" title="Собираем показатели" text="Подождите секунду." />;

  const year = new Date().getFullYear();
  const stats: [string, number][] = [
    ["Занимающихся в реестре", data.athletes], [`Соревнований в ${year}`, data.competitions_this_year],
    [`Участников в ${year}`, data.participants_this_year], [`Присвоено разрядов в ${year}`, data.ranks_this_year],
    ["Тренеров", data.coaches], ["Судей", data.judges], ["Организаций", data.organizations],
  ];

  return (
    <>
      <div className="stat-grid">
        {stats.map(([label, value]) => <div key={label} className="stat"><strong>{value}</strong><span>{label}</span></div>)}
      </div>
      <div className="cabinet-grid dashboard-grid">
        <div className="stack">
          <section className="card">
            <h2>Требует внимания</h2>
            {data.attention.length === 0 && <p className="muted">Всё рассмотрено — новых заявок и просроченных дел нет.</p>}
            <ul className="ref-list">
              {data.attention.map((item) => <li key={item.title}><Link to={item.link}>{item.title}</Link><span className="counter-badge">{item.count}</span></li>)}
            </ul>
          </section>
          <section className="card">
            <h2>Сроки</h2>
            <ul className="deadline-list">
              {data.deadlines.slice(0, 12).map((item) => (
                <li key={`${item.kind}-${item.title}-${item.date}`} className={`deadline deadline--${item.severity}`}>
                  <span className="deadline-date"><strong>{formatDate(item.date)}</strong><small>{daysLeftText(item.days_left)}</small></span>
                  {item.link ? <Link to={item.link}>{item.title}</Link> : <span>{item.title}</span>}
                </li>
              ))}
            </ul>
          </section>
        </div>
        <section className="card">
          <h2>Ближайшие соревнования</h2>
          {data.upcoming.length === 0 && <p className="muted">Предстоящих соревнований нет. <Link to="/admin/competitions">Создать соревнование</Link></p>}
          <ul className="ref-list">
            {data.upcoming.map((item) => (
              <li key={item.id}>
                <span><Link to={`/admin/competitions/${item.id}`}>{item.title}</Link><br /><small className="muted">{formatDate(item.date)} · {item.discipline}</small></span>
                <span className="row-actions"><StatusBadge status={item.status} /><small className="muted">допущено {item.approved}{item.pending ? `, ждут ${item.pending}` : ""}</small></span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

export function AdminDashboardPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Дашборд" />
      <AdminGate><DashboardView /></AdminGate>
    </section>
  );
}
