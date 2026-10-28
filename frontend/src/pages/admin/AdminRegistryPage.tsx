import { useEffect, useMemo, useState } from "react";
import { useSession } from "../../app/session";
import { api, errorText, fileUrl } from "../../shared/api";
import { birthYear, changeText, keys, rankLabels, stageLabels } from "../../shared/labels";
import type { Headcount, RegistryRow } from "../../shared/types";
import { PageTitle, State } from "../../shared/ui";
import { ValidityBadge } from "../../shared/widgets";
import { AdminGate } from "./AdminGate";

const FILTERS = ["q", "discipline_id", "organization_id", "municipality_id", "age_group_id", "min_rank"] as const;
type Filter = (typeof FILTERS)[number];

function Registry() {
  const { reference } = useSession();
  const [filters, setFilters] = useState<Record<Filter, string>>({ q: "", discipline_id: "", organization_id: "", municipality_id: "", age_group_id: "", min_rank: "" });
  const [rows, setRows] = useState<RegistryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => new URLSearchParams(FILTERS.filter((key) => filters[key]).map((key) => [key, filters[key]])).toString(), [filters]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api<RegistryRow[]>(`/registry/athletes?${query}`).then(setRows).catch((reason) => setError(errorText(reason)));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  const set = (name: Filter) => (event: { target: { value: string } }) => setFilters({ ...filters, [name]: event.target.value });

  return (
    <>
      <form className="filters filters--registry" onSubmit={(event) => event.preventDefault()}>
        <label>Поиск по ФИО<input value={filters.q} onChange={set("q")} placeholder="Фамилия или имя" /></label>
        <label>Дисциплина<select value={filters.discipline_id} onChange={set("discipline_id")}><option value="">Все</option>{reference?.disciplines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Организация<select value={filters.organization_id} onChange={set("organization_id")}><option value="">Все</option><option value="0">Без организации</option>{reference?.organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Муниципалитет<select value={filters.municipality_id} onChange={set("municipality_id")}><option value="">Все</option>{reference?.municipalities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Возрастная группа<select value={filters.age_group_id} onChange={set("age_group_id")}><option value="">Все</option>{reference?.age_groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Разряд не ниже<select value={filters.min_rank} onChange={set("min_rank")}><option value="">Любой</option>{keys(rankLabels).map((rank) => <option key={rank} value={rank}>{rankLabels[rank]}</option>)}</select></label>
      </form>
      {error && <State code="ERR" title="Реестр не загрузился" text={error} />}
      {rows?.length === 0 && <State code="00" title="Никого не нашли" text="Измените фильтры." />}
      {rows && rows.length > 0 && (
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>Спортсмен</th><th>Г. р.</th><th>Дисциплины</th><th>Организация</th><th>Занимается</th><th>Этап</th><th>Разряд</th><th>Тренеры</th><th /></tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.full_name}<br /><small className="muted">{row.municipality ?? "—"}</small></td>
                  <td>{birthYear(row.birth_date)}</td>
                  <td>{row.disciplines.map((item) => item.name.replace("Программирование ", "")).join(", ")}</td>
                  <td>{row.organization ?? "без организации"}</td>
                  <td>{row.start_year ? `с ${row.start_year}` : "—"}{row.end_year ? ` по ${row.end_year}` : ""}</td>
                  <td>{row.training_stage ? stageLabels[row.training_stage] : "—"}</td>
                  <td>{row.rank ? <>{rankLabels[row.rank]} <ValidityBadge validity={row.rank_validity} /></> : "—"}</td>
                  <td>{row.coaches.join("; ") || "—"}</td>
                  <td><a className="link-button" href={fileUrl(`/athletes/${row.id}/report.docx`)}>Отчёт .docx</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rows && <p className="muted">Найдено: {rows.length}</p>}
    </>
  );
}

export function HeadcountView() {
  const year = new Date().getFullYear();
  const [period, setPeriod] = useState({ from_year: year - 2, to_year: year });
  const [report, setReport] = useState<Headcount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = `from_year=${period.from_year}&to_year=${period.to_year}`;

  useEffect(() => {
    setError(null);
    api<Headcount>(`/reports/headcount?${query}`).then(setReport).catch((reason) => setError(errorText(reason)));
  }, [query]);

  const years = Array.from({ length: 10 }, (_, index) => year - 9 + index);
  return (
    <>
      <div className="inline-form">
        <label className="inline-label">С<select value={period.from_year} onChange={(event) => setPeriod({ ...period, from_year: Number(event.target.value) })}>{years.filter((item) => item < period.to_year).map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label className="inline-label">по<select value={period.to_year} onChange={(event) => setPeriod({ ...period, to_year: Number(event.target.value) })}>{years.filter((item) => item > period.from_year).map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <a className="button button--small" href={fileUrl(`/reports/headcount.xlsx?${query}`)}>Скачать .xlsx</a>
      </div>
      {error && <State code="ERR" title="Отчёт не сформирован" text={error} />}
      {report && (
        <>
          <div className="stat-grid">
            {report.years.map((item, index) => <div key={item} className="stat"><strong>{report.total[index]}</strong><span>занимающихся в {item}</span></div>)}
            <div className="stat"><strong>{changeText(report.total)}</strong><span>динамика {report.years[report.years.length - 1]} к {report.years[report.years.length - 2]}</span></div>
          </div>
          <div className="ref-grid">
            {report.sections.map((section) => (
              <section key={section.key} className="card">
                <h2>{section.title}</h2>
                <div className="table-wrap">
                  <table className="protocol-table">
                    <thead><tr><th>{section.title}</th>{report.years.map((item) => <th key={item}>{item}</th>)}<th>Динамика</th></tr></thead>
                    <tbody>
                      {section.rows.map((line) => <tr key={line.name}><td>{line.name}</td>{line.counts.map((count, index) => <td key={index}>{count}</td>)}<td>{changeText(line.counts)}</td></tr>)}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
          <p className="muted">{report.note}</p>
        </>
      )}
    </>
  );
}

export function AdminRegistryPage() {
  const [tab, setTab] = useState<"registry" | "headcount">("registry");
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Реестр занимающихся" />
      <AdminGate>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "registry"} className={tab === "registry" ? "is-active" : ""} onClick={() => setTab("registry")}>Спортсмены</button>
          <button type="button" role="tab" aria-selected={tab === "headcount"} className={tab === "headcount" ? "is-active" : ""} onClick={() => setTab("headcount")}>Численность и динамика</button>
        </div>
        {tab === "registry" ? <Registry /> : <HeadcountView />}
      </AdminGate>
    </section>
  );
}
