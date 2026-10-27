import { useCallback, useEffect, useState } from "react";
import { api, errorText } from "../../shared/api";
import { categoryLabels, categoryValidityYears, formatDate, requestKindLabels } from "../../shared/labels";
import type { JudgeRequest, JudgeRow } from "../../shared/types";
import { PageTitle, State } from "../../shared/ui";
import { DecisionForm, ValidityBadge } from "../../shared/widgets";
import { AdminGate } from "./AdminGate";

function JudgesView() {
  const [judges, setJudges] = useState<JudgeRow[]>([]);
  const [requests, setRequests] = useState<JudgeRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const load = useCallback(() => {
    Promise.all([api<JudgeRow[]>("/judges"), api<JudgeRequest[]>("/judge-requests?status=pending")])
      .then(([a, b]) => { setJudges(a); setRequests(b); setLoaded(true); })
      .catch((reason) => setError(errorText(reason)));
  }, []);
  useEffect(load, [load]);
  if (error) return <State code="ERR" title="Не удалось загрузить" text={error} />;
  if (!loaded) return <State code="…" title="Загружаем" text="Подождите секунду." />;

  return (
    <div className="ref-grid">
      <section className="card card--wide">
        <h2>Заявки на присвоение и подтверждение категории</h2>
        {requests.length === 0 && <p className="muted">Новых заявок нет.</p>}
        <ul className="ref-list">
          {requests.map((item) => (
            <li key={item.id} className="stacked">
              <span>
                <strong>{item.judge_name}</strong> — {requestKindLabels[item.kind].toLowerCase()}: <strong>{categoryLabels[item.category]}</strong><br />
                <small className="muted">Текущая: {item.current.category ? `${categoryLabels[item.current.category]} до ${formatDate(item.current.category_expires_on)}` : "нет"} · подана {formatDate(item.created_at)}</small>
                <p className="quote">{item.justification}</p>
              </span>
              <DecisionForm path={`/judge-requests/${item.id}/decision`} defaultYears={categoryValidityYears[item.category]} onDone={load} />
            </li>
          ))}
        </ul>
      </section>
      <section className="card card--wide">
        <h2>Реестр судей</h2>
        {judges.length === 0 && <p className="muted">Судей пока нет — пользователь добавляет себе роль судьи в кабинете.</p>}
        <div className="table-wrap">
          {judges.length > 0 && (
            <table className="protocol-table">
              <thead><tr><th>Судья</th><th>Категория</th><th>Срок действия</th><th>Приказ</th><th>Назначений</th></tr></thead>
              <tbody>
                {judges.map((item) => (
                  <tr key={item.judge_id}>
                    <td>{item.name}</td>
                    <td>{item.info.category ? categoryLabels[item.info.category] : "—"}</td>
                    <td><ValidityBadge validity={item.info.validity} until={item.info.category_expires_on} /></td>
                    <td>{item.info.order_ref ?? "—"}</td>
                    <td>{item.assignments}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}

export function AdminJudgesPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Судьи и категории" />
      <AdminGate><JudgesView /></AdminGate>
    </section>
  );
}
