import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../../shared/api";
import { formatDate, levelLabels, rankLabels, rankValidityYears, requestKindLabels, requestStatusLabels } from "../../shared/labels";
import type { CompetitionLevel, RankCandidate, RankRecord, RankRequest, SportRank } from "../../shared/types";
import { PageTitle, State } from "../../shared/ui";
import { DecisionForm, ValidityBadge } from "../../shared/widgets";
import { AdminGate } from "./AdminGate";

type Expiring = { athlete: RankRequest["athlete"]; rank: RankRecord };
type Norm = { level: CompetitionLevel; max_place: number; rank: SportRank };

function Requests({ items, reload }: { items: RankRequest[]; reload: () => void }) {
  const pending = items.filter((item) => item.status === "pending");
  const decided = items.filter((item) => item.status !== "pending").slice(0, 20);
  return (
    <section className="card card--wide">
      <h2>Заявки на разряд</h2>
      {pending.length === 0 && <p className="muted">Новых заявок нет.</p>}
      <ul className="ref-list">
        {pending.map((item) => (
          <li key={item.id} className="stacked">
            <div className="row-split">
              <span>
                <strong>{item.athlete.full_name}</strong> — {requestKindLabels[item.kind].toLowerCase()}: <strong>{rankLabels[item.rank]}</strong><br />
                <small className="muted">
                  Основание: <Link to={`/competitions/${item.basis.competition.id}/protocol`}>«{item.basis.competition.title}»</Link> ({levelLabels[item.basis.competition.level]}, {formatDate(item.basis.competition.date)}) — {item.basis.place ?? "—"} место, {item.basis.score ?? "—"} баллов.
                  Подал: {item.submitted_by} ({item.submitted_role === "coach" ? "тренер" : "спортсмен"}). Текущий разряд: {item.current ? `${rankLabels[item.current.rank]} до ${formatDate(item.current.expires_on)}` : "нет"}.
                </small>
              </span>
            </div>
            <DecisionForm path={`/rank-requests/${item.id}/decision`} defaultYears={rankValidityYears[item.rank]} onDone={reload} />
          </li>
        ))}
      </ul>
      {decided.length > 0 && (
        <details>
          <summary className="muted">Рассмотренные заявки ({decided.length})</summary>
          <ul className="ref-list">
            {decided.map((item) => (
              <li key={item.id}><span>{item.athlete.full_name} — {rankLabels[item.rank]}{item.moderator_comment ? ` · ${item.moderator_comment}` : ""}</span><span className={`app-status app-status--${item.status}`}>{requestStatusLabels[item.status]}</span></li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function RanksView() {
  const [requests, setRequests] = useState<RankRequest[]>([]);
  const [candidates, setCandidates] = useState<RankCandidate[]>([]);
  const [expiring, setExpiring] = useState<Expiring[]>([]);
  const [norms, setNorms] = useState<Norm[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const load = useCallback(() => {
    Promise.all([api<RankRequest[]>("/rank-requests"), api<RankCandidate[]>("/rank-candidates"), api<Expiring[]>("/ranks/expiring"), api<Norm[]>("/rank-norms")])
      .then(([a, b, c, d]) => { setRequests(a); setCandidates(b); setExpiring(c); setNorms(d); setLoaded(true); })
      .catch((reason) => setError(errorText(reason)));
  }, []);
  useEffect(load, [load]);
  if (error) return <State code="ERR" title="Не удалось загрузить" text={error} />;
  if (!loaded) return <State code="…" title="Загружаем" text="Подождите секунду." />;

  return (
    <div className="ref-grid">
      <Requests items={requests} reload={load} />
      <section className="card">
        <h2>Кандидаты по протоколам</h2>
        <p className="muted">Результат в опубликованном протоколе может соответствовать требованиям ЕВСК выше текущего разряда.</p>
        {candidates.length === 0 && <p className="muted">Кандидатов нет.</p>}
        <ul className="ref-list">
          {candidates.map((item) => (
            <li key={item.athlete.id}>
              <span>{item.athlete.full_name}<br /><small className="muted">«{item.basis.competition.title}» — {item.basis.place} место ({levelLabels[item.basis.competition.level]})</small></span>
              <span className="row-actions"><span className="tag">{rankLabels[item.suggested_rank]}</span>{item.pending_request && <small className="muted">заявка подана</small>}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="card">
        <h2>Истекающие разряды</h2>
        {expiring.length === 0 && <p className="muted">В ближайшие 60 дней разряды не истекают.</p>}
        <ul className="ref-list">
          {expiring.map((item) => <li key={item.rank.id}><span>{item.athlete.full_name}<br /><small className="muted">{rankLabels[item.rank.rank]}, {item.rank.order_ref}</small></span><ValidityBadge validity={item.rank.validity} until={item.rank.expires_on} /></li>)}
        </ul>
      </section>
      <section className="card card--wide">
        <h2>Ориентиры ЕВСК для подсветки</h2>
        <p className="muted">Какое место на соревновании какого статуса даёт право на разряд. Значения федерация сверяет с действующей ЕВСК.</p>
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>Статус соревнования</th><th>Место не ниже</th><th>Разряд</th></tr></thead>
            <tbody>{norms.map((item) => <tr key={`${item.level}-${item.max_place}`}><td>{levelLabels[item.level]}</td><td>{item.max_place}</td><td>{rankLabels[item.rank]}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function AdminRanksPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Спортивные разряды" />
      <AdminGate><RanksView /></AdminGate>
    </section>
  );
}
