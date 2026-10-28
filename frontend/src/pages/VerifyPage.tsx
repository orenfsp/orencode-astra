import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText } from "../shared/api";
import { formatDate, formatRange, levelLabels } from "../shared/labels";
import type { Verification } from "../shared/types";
import { State } from "../shared/ui";

/** Публичная проверка подлинности справки по QR-коду. */
export function VerifyPage() {
  const { code } = useParams();
  const [data, setData] = useState<Verification | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Verification>(`/verify/${code}`).then(setData).catch((reason) => setError(errorText(reason)));
  }, [code]);

  return (
    <section className="section narrow">
      <span className="eyebrow">Проверка подлинности справки</span>
      {!data && !error && <State code="…" title="Проверяем" text="Ищем справку по коду." />}
      {error && <State code="✕" title="Справка не найдена" text="Такая справка платформой ФСП Оренбургской области не выдавалась. Проверьте ссылку или QR-код." />}
      {data && (
        <article className="card verify-card">
          <p className="verify-ok">✓ Справка подлинная</p>
          <h1 className="detail-title">№ {data.number}</h1>
          <p className="muted">Выдана {formatDate(data.issued_at)} платформой Федерации спортивного программирования Оренбургской области</p>
          <dl className="detail-grid verify-grid">
            <div><dt>Спортсмен</dt><dd>{data.athlete}{data.birth_year ? `, ${data.birth_year} г. р.` : ""}</dd></div>
            <div><dt>Соревнование</dt><dd>{data.competition.title}</dd></div>
            <div><dt>Статус</dt><dd>{levelLabels[data.competition.level]}, {data.competition.competition_type.name.toLowerCase()}</dd></div>
            <div><dt>Дисциплина</dt><dd>{data.competition.discipline.name}</dd></div>
            <div><dt>Даты и место</dt><dd>{formatRange(data.competition.date, data.competition.end_date)}, {data.location}</dd></div>
            <div><dt>Возрастная группа</dt><dd>{data.age_group}</dd></div>
            <div><dt>Результат</dt><dd>{data.place ? `${data.place} место из ${data.participants}` : data.result}{data.place ? ` · ${data.result} баллов` : ""}</dd></div>
          </dl>
          <Link className="button button--ghost" to={`/competitions/${data.competition.id}/protocol`}>Открыть протокол соревнования</Link>
        </article>
      )}
    </section>
  );
}
