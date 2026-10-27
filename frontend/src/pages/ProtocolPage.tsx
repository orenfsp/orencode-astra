import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText, fileUrl } from "../shared/api";
import { birthYear, formatDate, formatRange, levelLabels, resultStatusLabels } from "../shared/labels";
import type { Protocol } from "../shared/types";
import { State } from "../shared/ui";

export function ProtocolTable({ protocol }: { protocol: Protocol }) {
  return (
    <>
      {protocol.groups.length === 0 && <State code="00" title="Участников нет" text="В протокол попадают спортсмены с одобренными заявками." />}
      {protocol.groups.map((group) => (
        <section key={group.age_group.id} className="protocol-group">
          <h2>{group.age_group.name}</h2>
          <div className="table-wrap">
            <table className="protocol-table">
              <thead><tr><th>Место</th><th>Спортсмен</th><th>Г. р.</th><th>Муниципалитет</th><th>Организация</th><th>Баллы</th></tr></thead>
              <tbody>
                {group.rows.map((row) => (
                  <tr key={row.application_id} className={row.place !== null && row.place <= 3 ? "is-podium" : ""}>
                    <td className="place">{row.place ?? "—"}</td>
                    <td>{row.athlete.full_name}</td>
                    <td>{birthYear(row.athlete.birth_date)}</td>
                    <td>{row.athlete.municipality ?? "—"}</td>
                    <td>{row.athlete.organization ?? "без организации"}</td>
                    <td>{row.result_status === null ? <span className="muted">нет результата</span> : row.result_status === "ok" ? row.score : resultStatusLabels[row.result_status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </>
  );
}

export function ProtocolPage() {
  const { id } = useParams();
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Protocol>(`/competitions/${id}/protocol`).then(setProtocol).catch((reason) => setError(errorText(reason)));
  }, [id]);

  return (
    <section className="section protocol">
      <Link className="back-link no-print" to={`/competitions/${id}`}>← К соревнованию</Link>
      {!protocol && !error && <State code="…" title="Загружаем протокол" text="Подождите секунду." />}
      {error && <State code="404" title="Протокол недоступен" text={error} />}
      {protocol && (
        <>
          <div className="page-title">
            <span className="eyebrow">Протокол результатов · {levelLabels[protocol.competition.level]} · {protocol.competition.competition_type.name}</span>
            <h1>{protocol.competition.title}</h1>
            <p className="lead">{protocol.competition.discipline.name} · {formatRange(protocol.competition.date, protocol.competition.end_date)} · {protocol.location}</p>
            <p className="muted">{protocol.published_at ? `Опубликован ${formatDate(protocol.published_at)}` : "Черновик протокола — не опубликован"}</p>
          </div>
          <ProtocolTable protocol={protocol} />
          <div className="detail-actions no-print">
            <a className="button" href={fileUrl(`/competitions/${id}/protocol.docx`)}>Скачать протокол .docx</a>
            <button type="button" className="button button--ghost" onClick={() => window.print()}>Распечатать</button>
          </div>
        </>
      )}
    </section>
  );
}
