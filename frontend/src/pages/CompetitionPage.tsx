import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { API_BASE, api, errorText } from "../shared/api";
import { formatDate, formatLabels, formatRange, levelLabels, planLabels } from "../shared/labels";
import type { Competition } from "../shared/types";
import { State, StatusBadge } from "../shared/ui";

export function CompetitionPage() {
  const { id } = useParams();
  const [item, setItem] = useState<Competition | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Competition>(`/competitions/${id}`).then(setItem).catch((reason) => setError(errorText(reason)));
  }, [id]);

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
              ? <a className="button" href={`${API_BASE}/api/v1/competitions/${item.id}/regulation`}>Скачать положение</a>
              : <span className="muted">Положение будет опубликовано позже</span>}
          </div>
        </article>
      )}
    </section>
  );
}
