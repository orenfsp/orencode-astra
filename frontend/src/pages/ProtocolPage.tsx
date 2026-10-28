import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorText, fileUrl } from "../shared/api";
import { birthYear, formatDate, formatRange, levelLabels, resultStatusLabels } from "../shared/labels";
import type { Protocol, ProtocolRow } from "../shared/types";
import { State } from "../shared/ui";

/** «Тимофеев Борис Сергеевич» → «Б. С. Тимофеев», как в подписи протокола. */
export function initials(name: string | null): string {
  if (!name) return "";
  const [last, ...rest] = name.split(" ");
  return [...rest.map((part) => `${part[0]}.`), last].join(" ");
}

function Participant({ row }: { row: ProtocolRow }) {
  return (
    <>
      {row.athlete.full_name}
      <br /><small className="muted">{[birthYear(row.athlete.birth_date) !== "—" ? `${birthYear(row.athlete.birth_date)} г. р.` : null, row.athlete.organization ?? "без организации", row.athlete.municipality].filter(Boolean).join(", ")}</small>
    </>
  );
}

function outcome(row: ProtocolRow): string | null {
  if (row.result_status === null) return "нет результата";
  return row.result_status === "ok" ? null : resultStatusLabels[row.result_status];
}

function TasksTable({ rows, taskCount }: { rows: ProtocolRow[]; taskCount: number }) {
  const numbers = Array.from({ length: taskCount }, (_, index) => index + 1);
  return (
    <table className="protocol-table protocol-table--form">
      <thead>
        <tr><th rowSpan={2}>№ п/п</th><th rowSpan={2}>Участник (состав)</th><th colSpan={taskCount} className="center">Задачи</th><th rowSpan={2}>Решено</th><th rowSpan={2}>Время выполнения задач, мин</th></tr>
        <tr>{numbers.map((number) => <th key={number} className="center">{number}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const status = outcome(row);
          return (
            <tr key={row.application_id} className={row.place !== null && row.place <= 3 ? "is-podium" : ""}>
              <td className="place">{row.place ?? "—"}</td>
              <td><Participant row={row} /></td>
              {numbers.map((number) => {
                const mark = row.task_marks?.[number - 1] ?? "";
                return <td key={number} className={`mark${mark.startsWith("+") ? " mark--solved" : mark ? " mark--failed" : ""}`}>{mark}</td>;
              })}
              <td>{status ? <span className="muted">{status}</span> : <strong>{row.solved ?? row.score}</strong>}</td>
              <td>{status ? "" : row.penalty_minutes ?? "—"}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function ScoreTable({ rows }: { rows: ProtocolRow[] }) {
  return (
    <table className="protocol-table">
      <thead><tr><th>Место</th><th>Участник</th><th>Баллы</th></tr></thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.application_id} className={row.place !== null && row.place <= 3 ? "is-podium" : ""}>
            <td className="place">{row.place ?? "—"}</td>
            <td><Participant row={row} /></td>
            <td>{outcome(row) ? <span className="muted">{outcome(row)}</span> : row.score}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ProductTable({ rows, criteria }: { rows: ProtocolRow[]; criteria: string[] }) {
  return (
    <table className="protocol-table protocol-table--form">
      <thead>
        <tr><th>Место</th><th>Команда (состав)</th><th>Судья</th>{criteria.map((item) => <th key={item} className="center criterion">{item} (10%)</th>)}<th>ИТОГО</th></tr>
      </thead>
      {rows.map((row) => {
        const judges = row.judge_scores ?? [];
        const span = judges.length + 1;
        const status = outcome(row);
        return (
          <tbody key={row.application_id} className={`team-block${row.place !== null && row.place <= 3 ? " is-podium" : ""}`}>
            {judges.map((judge, index) => (
              <tr key={index}>
                {index === 0 && <><td rowSpan={span} className="place">{row.place ?? "—"}</td><td rowSpan={span}><Participant row={row} /></td></>}
                <td>{judge.judge}</td>
                {judge.scores.map((score, column) => <td key={column} className="center">{score}</td>)}
                <td className="center">{judge.total}</td>
              </tr>
            ))}
            <tr className="overall">
              {judges.length === 0 && <><td className="place">{row.place ?? "—"}</td><td><Participant row={row} /></td></>}
              <td><strong>ОБЩЕЕ</strong></td>
              {criteria.map((item, column) => <td key={item} className="center">{row.overall_scores?.[column] ?? ""}</td>)}
              <td className="center"><strong>{status ?? row.score}</strong></td>
            </tr>
          </tbody>
        );
      })}
    </table>
  );
}

export function ProtocolTable({ protocol }: { protocol: Protocol }) {
  const taskCount = protocol.task_count ?? Math.max(0, ...protocol.groups.flatMap((group) => group.rows.map((row) => row.task_marks?.length ?? 0)));
  const summary = protocol.tasks_summary;
  return (
    <>
      {protocol.groups.length === 0 && <State code="00" title="Участников нет" text="В протокол попадают спортсмены с одобренными заявками." />}
      {protocol.groups.map((group) => (
        <section key={group.age_group.id} className="protocol-group">
          <h2>{group.age_group.name}</h2>
          <div className="table-wrap">
            {protocol.form === "product"
              ? <ProductTable rows={group.rows} criteria={protocol.criteria} />
              : taskCount > 0 ? <TasksTable rows={group.rows} taskCount={taskCount} /> : <ScoreTable rows={group.rows} />}
          </div>
        </section>
      ))}
      {summary && (
        <p>К решению были предложены {summary.offered ?? "—"} задач, кол-во команд, решивших все задачи: {summary.solved_all}; кол-во команд, не решивших ни одной задачи: {summary.solved_none}.</p>
      )}
      {protocol.groups.length > 0 && (
        <dl className="protocol-signatures">
          <div><dt>Главный судья соревнований</dt><dd>{initials(protocol.chief_judge) || <span className="muted">не назначен</span>}</dd></div>
          <div><dt>Главный секретарь соревнований</dt><dd>{initials(protocol.chief_secretary) || <span className="muted">не назначен</span>}</dd></div>
        </dl>
      )}
      <p className="muted small-print">
        Форма — рекомендуемый образец протокола из Приложения № 5 к Правилам вида спорта «спортивное программирование» (приказ Минспорта России от 11.08.2023 № 584).{" "}
        <Link to="/protocol-forms">Образцы протоколов</Link>
      </p>
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
            <span className="eyebrow">Протокол · {levelLabels[protocol.competition.level]} · {protocol.competition.competition_type.name}</span>
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
