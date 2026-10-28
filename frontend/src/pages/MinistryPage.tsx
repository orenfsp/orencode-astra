import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText, fileUrl } from "../shared/api";
import { formatDate, rankLabels } from "../shared/labels";
import type { Team } from "../shared/types";
import { PageTitle, State } from "../shared/ui";
import { AdminGate } from "./admin/AdminGate";
import { HeadcountView } from "./admin/AdminRegistryPage";
import { DevelopmentView, EffectivenessView } from "./admin/AnalyticsPage";

type Tab = "development" | "headcount" | "teams" | "effectiveness";

function Teams() {
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Team[]>("/teams").then(setTeams).catch((reason) => setError(errorText(reason))); }, []);
  if (error) return <State code="ERR" title="Не удалось загрузить" text={error} />;
  if (teams?.length === 0) return <State code="00" title="Составов пока нет" text="Федерация ещё не сформировала сборную." />;
  return (
    <div className="ref-grid">
      {teams?.map((team) => (
        <section key={team.id} className="card card--wide">
          <h2>{team.title}</h2>
          <p className="muted">{team.discipline.name} · сезон {team.season} · сформирован {formatDate(team.created_at)}</p>
          <div className="table-wrap">
            <table className="protocol-table">
              <thead><tr><th>№</th><th>Спортсмен</th><th>Организация</th><th>Разряд</th><th>Место в рейтинге</th><th>Баллы</th><th>Состав</th></tr></thead>
              <tbody>{team.members.map((member, index) => (
                <tr key={member.athlete.id}><td>{index + 1}</td><td>{member.athlete.full_name}</td><td>{member.athlete.organization ?? "без организации"}</td>
                  <td>{member.rank ? rankLabels[member.rank] : "—"}</td><td>{member.rating_place ?? "—"}</td><td>{member.rating_points ?? "—"}</td><td>{member.is_reserve ? "резерв" : "основной"}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <div className="row-actions start"><a className="button button--small" href={fileUrl(`/teams/${team.id}/list.docx`)}>Список .docx</a><a className="button button--small button--ghost" href={fileUrl(`/teams/${team.id}/order.docx`)}>Проект приказа .docx</a></div>
        </section>
      ))}
    </div>
  );
}

/** Кабинет министерства спорта: только чтение отчётов, календаря и составов сборной (Д9). */
export function MinistryPage() {
  const [tab, setTab] = useState<Tab>("development");
  const tabs: [Tab, string][] = [["development", "Показатели развития"], ["headcount", "Численность"], ["teams", "Сборная"], ["effectiveness", "Эффективность"]];
  return (
    <section className="section">
      <PageTitle eyebrow="Министерство физической культуры и спорта Оренбургской области" title="Кабинет министерства">
        <p className="lead">Только чтение: отчёты федерации, показатели развития, составы сборной. Календарь соревнований — <Link to="/">на главной</Link>.</p>
      </PageTitle>
      <AdminGate roles={["ministry", "federation_admin"]}>
        <div className="tabs" role="tablist">
          {tabs.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "is-active" : ""} onClick={() => setTab(key)}>{label}</button>)}
        </div>
        {tab === "development" && <DevelopmentView />}
        {tab === "headcount" && <HeadcountView />}
        {tab === "teams" && <Teams />}
        {tab === "effectiveness" && <EffectivenessView />}
      </AdminGate>
    </section>
  );
}
