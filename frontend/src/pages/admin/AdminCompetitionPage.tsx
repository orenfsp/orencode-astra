import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useSession } from "../../app/session";
import { api, errorText, json } from "../../shared/api";
import { applicationStatusLabels, birthYear, categoryLabels, formatDate, formatRange, keys, resultStatusLabels } from "../../shared/labels";
import type { Application, ApplicationStatus, Competition, JudgeAssignment, JudgeRow, Protocol, ResultStatus } from "../../shared/types";
import { FormError, Notice, PageTitle, State, StatusBadge } from "../../shared/ui";
import { ValidityBadge } from "../../shared/widgets";
import { ProtocolTable } from "../ProtocolPage";
import { AdminGate } from "./AdminGate";

type Tab = "applications" | "judges" | "results" | "protocol";

function JudgesTab({ competition }: { competition: Competition }) {
  const { reference } = useSession();
  const [panel, setPanel] = useState<JudgeAssignment[]>([]);
  const [judges, setJudges] = useState<JudgeRow[]>([]);
  const [form, setForm] = useState({ judge_id: "", position_id: "" });
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    api<JudgeAssignment[]>(`/competitions/${competition.id}/judges`).then(setPanel).catch((reason) => setError(errorText(reason)));
    api<JudgeRow[]>("/judges").then(setJudges).catch(() => setJudges([]));
  }, [competition.id]);
  useEffect(load, [load]);

  const assigned = new Set(panel.map((item) => item.judge_id));
  async function assign(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api(`/competitions/${competition.id}/judges`, json("POST", { judge_id: Number(form.judge_id), position_id: Number(form.position_id) }));
      setForm({ judge_id: "", position_id: form.position_id });
      load();
    } catch (reason) { setError(errorText(reason)); }
  }
  async function remove(item: JudgeAssignment) {
    setError(null);
    try { await api(`/competitions/${competition.id}/judges/${item.id}`, { method: "DELETE" }); load(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <>
      {panel.length === 0 && <State code="00" title="Коллегия не сформирована" text="Назначьте судей и их должности." />}
      {panel.length > 0 && (
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>Должность</th><th>Судья</th><th>Категория</th><th /></tr></thead>
            <tbody>
              {panel.map((item) => {
                const info = judges.find((judge) => judge.judge_id === item.judge_id)?.info;
                return (
                  <tr key={item.id}>
                    <td>{item.position.name}</td>
                    <td>{item.judge_name}</td>
                    <td>{info?.category ? <>{categoryLabels[info.category]} <ValidityBadge validity={info.validity} until={info.category_expires_on} /></> : <span className="muted">без категории</span>}</td>
                    <td className="row-actions"><button type="button" className="link-button danger" onClick={() => void remove(item)}>Снять</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <form className="inline-form" onSubmit={assign}>
        <select required value={form.judge_id} onChange={(event) => setForm({ ...form, judge_id: event.target.value })}>
          <option value="">Судья</option>
          {judges.filter((item) => !assigned.has(item.judge_id)).map((item) => <option key={item.judge_id} value={item.judge_id}>{item.name}{item.info.category ? ` — ${categoryLabels[item.info.category]}` : ""}</option>)}
        </select>
        <select required value={form.position_id} onChange={(event) => setForm({ ...form, position_id: event.target.value })}>
          <option value="">Должность</option>
          {reference?.judge_positions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button className="button button--small">Назначить</button>
      </form>
      {judges.length === 0 && <p className="muted">В реестре нет судей: пользователь добавляет себе роль судьи в кабинете.</p>}
      <FormError error={error} />
    </>
  );
}
type Draft = { score: string; result_status: ResultStatus };

function Applications({ items, reload }: { items: Application[]; reload: () => void }) {
  const [filter, setFilter] = useState<ApplicationStatus | "">("pending");
  const [error, setError] = useState<string | null>(null);
  const visible = filter ? items.filter((item) => item.status === filter) : items;

  async function decide(item: Application, status: "approved" | "rejected") {
    let comment: string | null = null;
    if (status === "rejected") {
      comment = window.prompt(`Причина отклонения заявки: ${item.athlete.full_name}`);
      if (!comment) return;
    }
    setError(null);
    try { await api(`/applications/${item.id}/decision`, json("POST", { status, comment })); reload(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <>
      <div className="chip-filter" role="group" aria-label="Фильтр по статусу">
        {(["", ...keys(applicationStatusLabels)] as (ApplicationStatus | "")[]).map((status) => (
          <button key={status || "all"} type="button" className={`role-chip${filter === status ? " is-active" : ""}`} onClick={() => setFilter(status)}>
            {status ? applicationStatusLabels[status] : "Все"} · {status ? items.filter((item) => item.status === status).length : items.length}
          </button>
        ))}
      </div>
      <FormError error={error} />
      {visible.length === 0 && <State code="00" title="Заявок нет" text={filter === "pending" ? "Все заявки рассмотрены." : "Под этот фильтр ничего не попало."} />}
      <div className="table-wrap">
        {visible.length > 0 && (
          <table className="protocol-table">
            <thead><tr><th>Спортсмен</th><th>Г. р.</th><th>Группа</th><th>Организация</th><th>Подана</th><th>Статус</th><th /></tr></thead>
            <tbody>
              {visible.map((item) => (
                <tr key={item.id}>
                  <td>{item.athlete.full_name}<br /><small className="muted">{item.athlete.municipality ?? ""}</small></td>
                  <td>{birthYear(item.athlete.birth_date)}</td>
                  <td>{item.age_group.name}</td>
                  <td>{item.athlete.organization ?? "без организации"}</td>
                  <td>{formatDate(item.created_at)}</td>
                  <td><span className={`app-status app-status--${item.status}`}>{applicationStatusLabels[item.status]}</span>{item.moderator_comment && <><br /><small className="muted">{item.moderator_comment}</small></>}</td>
                  <td className="row-actions">
                    {item.status === "pending" && <>
                      <button type="button" className="button button--small" onClick={() => void decide(item, "approved")}>Одобрить</button>
                      <button type="button" className="button button--small button--ghost" onClick={() => void decide(item, "rejected")}>Отклонить</button>
                    </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function Results({ competition, protocol, onSaved }: { competition: Competition; protocol: Protocol; onSaved: (protocol: Protocol) => void }) {
  const rows = useMemo(() => protocol.groups.flatMap((group) => group.rows.map((row) => ({ ...row, group: group.age_group.name }))), [protocol]);
  const [drafts, setDrafts] = useState<Record<number, Draft>>(() => Object.fromEntries(rows.map((row) => [row.application_id, { score: row.score ?? "", result_status: row.result_status ?? "ok" }])));
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const locked = Boolean(protocol.published_at);

  if (rows.length === 0) return <State code="00" title="Нет допущенных участников" text="Одобрите заявки — участники появятся здесь автоматически." />;

  const set = (id: number, patch: Partial<Draft>) => setDrafts({ ...drafts, [id]: { ...drafts[id], ...patch } });

  async function save() {
    setError(null); setNotice(null);
    const results = rows
      .map((row) => ({ application_id: row.application_id, ...drafts[row.application_id] }))
      .filter((item) => item.result_status !== "ok" || item.score.trim() !== "")
      .map((item) => ({ application_id: item.application_id, result_status: item.result_status, score: item.result_status === "ok" ? item.score.replace(",", ".") : null }));
    if (results.length === 0) { setError("Введите хотя бы один результат"); return; }
    try {
      onSaved(await api<Protocol>(`/competitions/${competition.id}/results`, json("PUT", { results })));
      setNotice("Результаты сохранены, места пересчитаны");
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <>
      {locked && <State code="LOCK" title="Протокол опубликован" text="Чтобы исправить результаты, снимите публикацию на вкладке «Протокол»." />}
      <div className="table-wrap">
        <table className="protocol-table">
          <thead><tr><th>Место</th><th>Спортсмен</th><th>Группа</th><th>Итог</th><th>Баллы</th></tr></thead>
          <tbody>
            {rows.map((row) => {
              const draft = drafts[row.application_id];
              return (
                <tr key={row.application_id}>
                  <td className="place">{row.place ?? "—"}</td>
                  <td>{row.athlete.full_name}</td>
                  <td>{row.group}</td>
                  <td>
                    <select aria-label={`Итог: ${row.athlete.full_name}`} disabled={locked} value={draft.result_status} onChange={(event) => set(row.application_id, { result_status: event.target.value as ResultStatus })}>
                      {keys(resultStatusLabels).map((status) => <option key={status} value={status}>{resultStatusLabels[status]}</option>)}
                    </select>
                  </td>
                  <td>
                    <input aria-label={`Баллы: ${row.athlete.full_name}`} className="score-input" inputMode="decimal" disabled={locked || draft.result_status !== "ok"}
                      value={draft.result_status === "ok" ? draft.score : ""} onChange={(event) => set(row.application_id, { score: event.target.value })} placeholder="0" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted">Места рассчитываются автоматически по баллам внутри возрастной группы; равные баллы делят место.</p>
      <FormError error={error} /><Notice text={notice} />
      {!locked && <button type="button" className="button" onClick={() => void save()}>Сохранить результаты</button>}
    </>
  );
}

function ProtocolTab({ competition, protocol, onChange }: { competition: Competition; protocol: Protocol; onChange: (protocol: Protocol) => void }) {
  const [error, setError] = useState<string | null>(null);
  async function run(path: string) {
    setError(null);
    try { onChange(await api<Protocol>(`/competitions/${competition.id}/protocol/${path}`, { method: "POST" })); } catch (reason) { setError(errorText(reason)); }
  }
  return (
    <>
      <div className="role-add">
        {protocol.published_at ? (
          <>
            <span className="app-status app-status--approved">Опубликован {formatDate(protocol.published_at)}</span>
            <Link className="button button--small" to={`/competitions/${competition.id}/protocol`}>Открыть публичную страницу</Link>
            <button type="button" className="link-button" onClick={() => void run("unpublish")}>Снять публикацию</button>
          </>
        ) : (
          <>
            <span className="app-status app-status--pending">Не опубликован</span>
            <button type="button" className="button button--small" disabled={!protocol.is_complete} onClick={() => void run("publish")}>Опубликовать протокол</button>
            {!protocol.is_complete && <span className="muted">Сначала внесите результаты всем допущенным участникам.</span>}
          </>
        )}
      </div>
      <FormError error={error} />
      <ProtocolTable protocol={protocol} />
    </>
  );
}

function Manage({ competitionId }: { competitionId: string }) {
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [protocol, setProtocol] = useState<Protocol | null>(null);
  const [tab, setTab] = useState<Tab>("applications");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api<Competition>(`/competitions/${competitionId}`),
      api<Application[]>(`/competitions/${competitionId}/applications`),
      api<Protocol>(`/competitions/${competitionId}/protocol`),
    ]).then(([nextCompetition, nextApplications, nextProtocol]) => {
      setCompetition(nextCompetition); setApplications(nextApplications); setProtocol(nextProtocol);
    }).catch((reason) => setError(errorText(reason)));
  }, [competitionId]);

  useEffect(load, [load]);

  if (error) return <State code="ERR" title="Не удалось загрузить" text={error} />;
  if (!competition || !protocol) return <State code="…" title="Загружаем" text="Заявки и протокол." />;

  const pending = applications.filter((item) => item.status === "pending").length;
  const approved = applications.filter((item) => item.status === "approved").length;

  return (
    <>
      <PageTitle eyebrow={`Кабинет федерации · ${competition.discipline.name}`} title={competition.title}>
        <p className="lead"><StatusBadge status={competition.status} /> {formatRange(competition.date, competition.end_date)} · заявок на модерации: {pending} · допущено: {approved}</p>
      </PageTitle>
      <div className="tabs" role="tablist">
        {([["applications", `Заявки${pending ? ` · ${pending}` : ""}`], ["judges", "Судейская коллегия"], ["results", "Результаты"], ["protocol", "Протокол"]] as [Tab, string][]).map(([key, label]) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "is-active" : ""} onClick={() => { setTab(key); load(); }}>{label}</button>
        ))}
      </div>
      {tab === "applications" && <Applications items={applications} reload={load} />}
      {tab === "judges" && <JudgesTab competition={competition} />}
      {tab === "results" && <Results key={protocol.groups.map((group) => group.rows.length).join("-") + (protocol.published_at ?? "")} competition={competition} protocol={protocol} onSaved={setProtocol} />}
      {tab === "protocol" && <ProtocolTab competition={competition} protocol={protocol} onChange={(next) => { setProtocol(next); load(); }} />}
    </>
  );
}

export function AdminCompetitionPage() {
  const { id } = useParams();
  return (
    <section className="section">
      <Link className="back-link" to="/admin/competitions">← Все соревнования</Link>
      <AdminGate>{id && <Manage competitionId={id} />}</AdminGate>
    </section>
  );
}
