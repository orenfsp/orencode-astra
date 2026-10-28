import { Fragment, useEffect, useState } from "react";
import { api, errorText } from "../../shared/api";
import { roleLabels } from "../../shared/labels";
import type { Role } from "../../shared/types";
import { PageTitle, State } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

type Entry = {
  id: number;
  created_at: string;
  user_id: number | null;
  user_name: string;
  role: Role | null;
  action: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  changes: Record<string, unknown> | null;
};
type Page = { total: number; items: Entry[]; entity_types: string[] };

const ACTIONS: Record<string, string> = { create: "Создание", update: "Изменение", status: "Смена статуса", delete: "Удаление" };
const PAGE_SIZE = 50;
const FIELD_LABELS: Record<string, string> = {
  status: "Статус", title: "Название", name: "Название", location: "Место", date: "Дата начала", end_date: "Дата окончания",
  level: "Уровень", format: "Формат", discipline_id: "Дисциплина", competition_type_id: "Тип соревнования", age_groups: "Возрастные группы",
  registration_start: "Приём заявок с", registration_end: "Приём заявок до", calendar_plan: "Календарный план", calendar_plan_number: "Номер в плане",
  regulation_filename: "Положение", protocol_published_at: "Протокол опубликован", is_archived: "В архиве", description: "Описание",
  category: "Категория", category_assigned_on: "Присвоена", category_expires_on: "Действует до", order_ref: "Приказ",
  rank: "Разряд", kind: "Вид", assigned_on: "Дата присвоения", expires_on: "Действует до", moderator_comment: "Комментарий федерации",
  score: "Баллы", place: "Место", result_status: "Итог", roles: "Роли", email: "Email", last_name: "Фамилия", first_name: "Имя",
  middle_name: "Отчество", birth_date: "Дата рождения", municipality_id: "Муниципалитет", organization_id: "Организация",
  disciplines: "Дисциплины", start_year: "Год начала занятий", end_year: "Год окончания занятий", training_stage: "Этап подготовки",
  reason: "Основание", starts_on: "С", ends_on: "По", position_id: "Должность", judge_id: "Судья", athlete_id: "Спортсмен",
  coach_id: "Тренер", age_group_id: "Возрастная группа", first: "1 место", second: "2 место", third: "3 место",
};

function formatMoment(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.map(show).join(", ") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function Changes({ entry }: { entry: Entry }) {
  const changes = entry.changes ?? {};
  const keys = Object.keys(changes);
  if (keys.length === 0) return <p className="muted">Подробностей нет.</p>;
  const isDiff = entry.action === "update" || entry.action === "status";
  return (
    <table className="protocol-table audit-changes">
      <thead><tr><th>Поле</th>{isDiff ? <><th>Было</th><th>Стало</th></> : <th>Значение</th>}</tr></thead>
      <tbody>
        {keys.map((key) => {
          const value = changes[key];
          const pair = isDiff && Array.isArray(value) ? value : null;
          return <tr key={key}><td title={key}>{FIELD_LABELS[key] ?? key}</td>{pair ? <><td>{show(pair[0])}</td><td>{show(pair[1])}</td></> : <td>{show(value)}</td>}</tr>;
        })}
      </tbody>
    </table>
  );
}

function AuditView() {
  const [filters, setFilters] = useState({ entity_type: "", action: "", q: "" });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(offset));
    const timer = window.setTimeout(() => {
      api<Page>(`/audit?${params}`).then(setPage).catch((reason) => setError(errorText(reason)));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [filters, offset]);

  const set = (name: keyof typeof filters) => (event: { target: { value: string } }) => { setOffset(0); setFilters({ ...filters, [name]: event.target.value }); };

  return (
    <>
      <form className="filters filters--registry" onSubmit={(event) => event.preventDefault()}>
        <label>Поиск<input value={filters.q} onChange={set("q")} placeholder="Название, фамилия, email" /></label>
        <label>Что изменено<select value={filters.entity_type} onChange={set("entity_type")}><option value="">Всё</option>{page?.entity_types.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
        <label>Действие<select value={filters.action} onChange={set("action")}><option value="">Все</option>{Object.entries(ACTIONS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      </form>
      {error && <State code="ERR" title="Журнал не загрузился" text={error} />}
      {page?.items.length === 0 && <State code="00" title="Записей нет" text="Здесь появятся создание, изменение и удаление записей, смена статусов и ввод результатов." />}
      {page && page.items.length > 0 && (
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>Когда</th><th>Кто</th><th>Роль</th><th>Действие</th><th>Что</th><th /></tr></thead>
            <tbody>
              {page.items.map((entry) => (
                <Fragment key={entry.id}>
                  <tr>
                    <td className="nowrap">{formatMoment(entry.created_at)}</td>
                    <td>{entry.user_name}</td>
                    <td>{entry.role ? roleLabels[entry.role] ?? entry.role : "—"}</td>
                    <td><span className={`app-status app-status--${entry.action === "delete" ? "rejected" : entry.action === "create" ? "approved" : "pending"}`}>{ACTIONS[entry.action] ?? entry.action}</span></td>
                    <td>{entry.summary}</td>
                    <td><button type="button" className="link-button" onClick={() => setOpen(open === entry.id ? null : entry.id)}>{open === entry.id ? "Скрыть" : "Подробно"}</button></td>
                  </tr>
                  {open === entry.id && <tr className="rating-detail"><td colSpan={6}><Changes entry={entry} /></td></tr>}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {page && page.total > PAGE_SIZE && (
        <div className="inline-form">
          <button type="button" className="button button--small button--ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Новее</button>
          <span className="muted">{offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} из {page.total}</span>
          <button type="button" className="button button--small button--ghost" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Старее →</button>
        </div>
      )}
    </>
  );
}

export function AdminAuditPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Журнал действий">
        <p className="lead">Кто, когда и в какой роли создал, изменил или удалил запись, сменил статус или внёс результаты.</p>
      </PageTitle>
      <AdminGate><AuditView /></AdminGate>
    </section>
  );
}
