import { StrictMode, useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { AuthPanel } from "./auth/AuthPanel";
import "./styles.css";

type CompetitionStatus =
  | "draft"
  | "registration_open"
  | "registration_closed"
  | "upcoming"
  | "ongoing"
  | "completed";

type Competition = {
  id: number;
  title: string;
  discipline: string;
  date: string;
  location: string;
  description: string;
  event_format: string;
  registration_start: string;
  registration_end: string;
  status: CompetitionStatus;
  is_archived: boolean;
};

type CompetitionPayload = Omit<Competition, "id" | "is_archived">;

const API_URL = "http://127.0.0.1:8002/api/v1/competitions";
const ALL_FILTER = "all";
const statusLabels: Record<CompetitionStatus, string> = {
  draft: "Черновик",
  upcoming: "Скоро",
  registration_open: "Регистрация открыта",
  registration_closed: "Регистрация закрыта",
  ongoing: "Идёт сейчас",
  completed: "Завершено",
};
const statuses = Object.keys(statusLabels) as CompetitionStatus[];
const emptyPayload: CompetitionPayload = {
  title: "",
  discipline: "",
  date: "",
  location: "",
  description: "",
  event_format: "Очно",
  registration_start: "",
  registration_end: "",
  status: "draft",
};

async function apiRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const csrf = document.cookie.split("; ").find((value) => value.startsWith("fsp_csrf="))?.split("=").slice(1).join("=");
  const mutating = init?.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase());
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(mutating && csrf ? { "X-CSRF-Token": csrf } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `Сервер ответил с кодом ${response.status}`;
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function formatDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "long", year: "numeric" }).format(parsed);
}

function Header() {
  return (
    <header className="site-header">
      <div className="header-main page-width">
        <a className="brand" href="/" aria-label="ФСП Оренбургская область">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span>
          <span className="brand-short">ФСП</span>
          <span className="brand-region">Оренбургская<br />область</span>
        </a>
        <div className="header-meta"><span className="region-code">REG / 56</span><span className="signal"><i /> Система работает</span></div>
      </div>
      <div className="header-nav">
        <nav className="page-width" aria-label="Основная навигация">
          <a href="/#competitions">Соревнования</a>
          <a href="/competitions/admin">Управление</a>
          <span>О федерации</span><span>Оренбург · UTC+5</span>
        </nav>
      </div>
    </header>
  );
}

function State({ code, title, text }: { code: string; title: string; text: string }) {
  return <div className="state" role={code === "ERR" ? "alert" : "status"}><span className="state-code">{code}</span><div><strong>{title}</strong><span>{text}</span></div></div>;
}

function CatalogPage() {
  const [catalog, setCatalog] = useState<Competition[]>([]);
  const [statusFilter, setStatusFilter] = useState(ALL_FILTER);
  const [disciplineFilter, setDisciplineFilter] = useState(ALL_FILTER);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<Competition[]>(API_URL).then(setCatalog).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);

  const disciplines = useMemo(() => Array.from(new Set(catalog.map((item) => item.discipline))).sort((a, b) => a.localeCompare(b, "ru")), [catalog]);
  const filtered = useMemo(() => catalog.filter((item) =>
    (statusFilter === ALL_FILTER || item.status === statusFilter)
    && (disciplineFilter === ALL_FILTER || item.discipline === disciplineFilter)
  ), [catalog, disciplineFilter, statusFilter]);
  const reset = () => { setStatusFilter(ALL_FILTER); setDisciplineFilter(ALL_FILTER); };

  return <>
    <section className="intro page-width" aria-labelledby="page-title"><div className="intro-copy"><span className="eyebrow">Региональный календарь / 2026</span><h1 id="page-title">Спортивное<br />программирование</h1></div><p>Турниры, чемпионаты и открытые соревнования<br className="desktop-break" /> Оренбургской области.</p></section>
    <section className="competitions page-width" id="competitions" aria-labelledby="competitions-title">
      <div className="section-heading"><div><span className="section-index">01</span><h2 id="competitions-title">Ближайшие события</h2></div>{!loading && !error && <span className="counter">{String(filtered.length).padStart(2, "0")} / {String(catalog.length).padStart(2, "0")}</span>}</div>
      {!loading && !error && catalog.length > 0 && <form className="filters" onSubmit={(event) => event.preventDefault()}>
        <div className="filter-field"><label htmlFor="status-filter">Статус</label><select id="status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value={ALL_FILTER}>Все статусы</option>{statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}</select></div>
        <div className="filter-field"><label htmlFor="discipline-filter">Дисциплина</label><select id="discipline-filter" value={disciplineFilter} onChange={(event) => setDisciplineFilter(event.target.value)}><option value={ALL_FILTER}>Все дисциплины</option>{disciplines.map((value) => <option key={value} value={value}>{value}</option>)}</select></div>
        {(statusFilter !== ALL_FILTER || disciplineFilter !== ALL_FILTER) && <button className="filter-reset" type="button" onClick={reset}>Сбросить</button>}
      </form>}
      {loading && <State code="…" title="Получаем календарь" text="Синхронизация с региональным API…" />}
      {error && <State code="ERR" title="Не удалось загрузить список" text={error} />}
      {!loading && !error && catalog.length === 0 && <State code="00" title="Событий пока нет" text="Новые соревнования появятся здесь после публикации." />}
      {!loading && !error && catalog.length > 0 && filtered.length === 0 && <div><State code="00" title="По выбранным фильтрам ничего нет" text="Измените параметры или сбросьте фильтры." /><button className="state-reset" type="button" onClick={reset}>Показать все события</button></div>}
      {!loading && !error && filtered.length > 0 && <div className="competition-list">{filtered.map((competition, index) => <a className="competition-row" href={`/competitions/${competition.id}`} key={competition.id}>
        <span className="row-number">{String(index + 1).padStart(2, "0")}</span><span className="competition-main"><span className="card-topline"><span className={`status status--${competition.status}`}><i />{statusLabels[competition.status]}</span><span className="discipline">{competition.discipline}</span></span><strong className="competition-title">{competition.title}</strong></span>
        <span className="competition-meta"><span><small>Дата</small>{formatDate(competition.date)}</span><span><small>Формат / место</small>{competition.event_format} · {competition.location}</span></span><span className="row-arrow" aria-hidden="true">↗</span>
      </a>)}</div>}
    </section>
  </>;
}

function DetailPage({ competitionId }: { competitionId: number }) {
  const [competition, setCompetition] = useState<Competition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiRequest<Competition>(`${API_URL}/${competitionId}`).then(setCompetition).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false)); }, [competitionId]);

  return <section className="detail page-width">
    <a className="back-link" href="/#competitions">← Вернуться к календарю</a>
    {loading && <State code="…" title="Загружаем соревнование" text="Получаем актуальные данные." />}
    {error && <State code="404" title="Соревнование не найдено" text={error} />}
    {competition && <article>
      <div className="detail-heading"><span className={`status status--${competition.status}`}><i />{statusLabels[competition.status]}</span><span className="discipline">{competition.discipline}</span><h1>{competition.title}</h1><p>{competition.description}</p></div>
      <dl className="detail-grid"><div><dt>Дата</dt><dd>{formatDate(competition.date)}</dd></div><div><dt>Место</dt><dd>{competition.location}</dd></div><div><dt>Формат проведения</dt><dd>{competition.event_format}</dd></div><div><dt>Начало регистрации</dt><dd>{formatDate(competition.registration_start)}</dd></div><div><dt>Окончание регистрации</dt><dd>{formatDate(competition.registration_end)}</dd></div></dl>
    </article>}
  </section>;
}

function CompetitionForm({ editing, onSaved, onCancel }: { editing: Competition | null; onSaved: () => void; onCancel: () => void }) {
  const [payload, setPayload] = useState<CompetitionPayload>(editing ? { title: editing.title, discipline: editing.discipline, date: editing.date, location: editing.location, description: editing.description, event_format: editing.event_format, registration_start: editing.registration_start, registration_end: editing.registration_end, status: editing.status } : emptyPayload);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = (name: keyof CompetitionPayload) => ({ value: payload[name], onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setPayload({ ...payload, [name]: event.target.value }) });
  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(null);
    try {
      if (editing) { const { status: _status, ...changes } = payload; await apiRequest(`${API_URL}/${editing.id}`, { method: "PATCH", body: JSON.stringify(changes) }); }
      else await apiRequest(API_URL, { method: "POST", body: JSON.stringify(payload) });
      onSaved();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Не удалось сохранить"); }
    finally { setSaving(false); }
  }
  return <form className="admin-form" onSubmit={submit}>
    <div className="admin-form-heading"><h2>{editing ? "Редактировать соревнование" : "Новое соревнование"}</h2>{editing && <button type="button" className="text-button" onClick={onCancel}>Отменить</button>}</div>
    <label>Название<input required maxLength={255} {...field("title")} /></label><label>Дисциплина<input required maxLength={255} {...field("discipline")} /></label>
    <label>Дата соревнования<input required type="date" {...field("date")} /></label><label>Место<input required maxLength={255} {...field("location")} /></label>
    <label>Формат<input required maxLength={120} {...field("event_format")} /></label>{!editing && <label>Первичный статус<select {...field("status")}>{statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}</select></label>}
    <label>Начало регистрации<input required type="date" {...field("registration_start")} /></label><label>Окончание регистрации<input required type="date" {...field("registration_end")} /></label>
    <label className="form-wide">Описание<textarea required maxLength={5000} rows={5} {...field("description")} /></label>
    {error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button" disabled={saving}>{saving ? "Сохраняем…" : editing ? "Сохранить изменения" : "Создать соревнование"}</button>
  </form>;
}

function AdminPage() {
  const [items, setItems] = useState<Competition[]>([]); const [editing, setEditing] = useState<Competition | null>(null); const [error, setError] = useState<string | null>(null); const [version, setVersion] = useState(0);
  const reload = () => setVersion((value) => value + 1);
  useEffect(() => { apiRequest<Competition[]>(`${API_URL}?include_archived=true`).then(setItems).catch((reason: Error) => setError(reason.message)); }, [version]);
  async function action(url: string, init?: RequestInit) { setError(null); try { await apiRequest(url, init); reload(); } catch (reason) { setError(reason instanceof Error ? reason.message : "Операция не выполнена"); } }
  return <section className="admin page-width"><span className="eyebrow">Кабинет федерации</span><h1>Управление соревнованиями</h1><p className="admin-warning">Изменения доступны только пользователю с активной ролью администратора федерации.</p>
    <CompetitionForm key={editing?.id ?? "new"} editing={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); reload(); }} />
    <div className="admin-list"><div className="section-heading"><div><span className="section-index">02</span><h2>Все записи</h2></div><span className="counter">{items.length}</span></div>{error && <p className="form-error" role="alert">{error}</p>}{items.map((item) => <article className={`admin-card${item.is_archived ? " is-archived" : ""}`} key={item.id}>
      <div><span className={`status status--${item.status}`}><i />{statusLabels[item.status]}</span>{item.is_archived && <span className="archive-label">Архив</span>}<h3>{item.title}</h3><p>{item.discipline} · {formatDate(item.date)}</p></div>
      <div className="admin-actions"><button type="button" onClick={() => setEditing(item)} disabled={item.is_archived}>Редактировать</button><select aria-label={`Статус: ${item.title}`} value={item.status} disabled={item.is_archived} onChange={(event) => void action(`${API_URL}/${item.id}/status`, { method: "PATCH", body: JSON.stringify({ status: event.target.value }) })}>{statuses.map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}</select>{item.status === "registration_open" && !item.is_archived && <button type="button" onClick={() => void action(`${API_URL}/${item.id}/close-registration`, { method: "POST" })}>Закрыть регистрацию</button>}{!item.is_archived && <button className="danger-button" type="button" onClick={() => void action(`${API_URL}/${item.id}/archive`, { method: "POST" })}>Архивировать</button>}</div>
    </article>)}</div>
  </section>;
}

function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  const detailMatch = path.match(/^\/competitions\/(\d+)$/);
  return <div className="app-shell"><Header /><div className="auth-zone page-width"><AuthPanel /></div><main>{path === "/competitions/admin" ? <AdminPage /> : detailMatch ? <DetailPage competitionId={Number(detailMatch[1])} /> : <CatalogPage />}</main><footer className="page-width"><span>ФСП / ОРЕНБУРГСКАЯ ОБЛАСТЬ</span><span>КОД · СПОРТ · СООБЩЕСТВО</span></footer></div>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
