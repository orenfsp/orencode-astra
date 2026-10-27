import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useSession } from "../../app/session";
import { api, errorText, json } from "../../shared/api";
import { formatLabels, formatRange, keys, levelLabels, planLabels, statusLabels } from "../../shared/labels";
import type { CalendarPlan, Competition, CompetitionLevel, CompetitionPayload, Reference } from "../../shared/types";
import { FormError, Notice, PageTitle, State, StatusBadge } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

function emptyPayload(reference: Reference): CompetitionPayload {
  return {
    title: "", discipline_id: reference.disciplines[0]?.id ?? 0, competition_type_id: reference.competition_types.find((item) => item.is_active)?.id ?? 0,
    level: "regional", age_group_ids: [], date: "", end_date: "", location: "", description: "", format: "offline",
    registration_start: "", registration_end: "", calendar_plan: "regional", calendar_plan_number: "", status: "draft",
  };
}

function toPayload(item: Competition): CompetitionPayload {
  return {
    title: item.title, discipline_id: item.discipline.id, competition_type_id: item.competition_type.id, level: item.level,
    age_group_ids: item.age_groups.map((group) => group.id), date: item.date, end_date: item.end_date, location: item.location,
    description: item.description, format: item.format, registration_start: item.registration_start, registration_end: item.registration_end,
    calendar_plan: item.calendar_plan, calendar_plan_number: item.calendar_plan_number ?? "",
  };
}

/** Подсказка по правилам: всероссийские и межрегиональные — в ЕКП, региональные — в план области. */
function expectedPlan(level: CompetitionLevel): CalendarPlan {
  return level === "regional" ? "regional" : "ekp";
}

function CompetitionForm({ reference, editing, onSaved, onCancel }: { reference: Reference; editing: Competition | null; onSaved: () => void; onCancel: () => void }) {
  const [form, setForm] = useState<CompetitionPayload>(editing ? toPayload(editing) : emptyPayload(reference));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = <K extends keyof CompetitionPayload>(name: K, value: CompetitionPayload[K]) => setForm((current) => ({ ...current, [name]: value }));
  const toggleGroup = (id: number) => set("age_group_ids", form.age_group_ids.includes(id) ? form.age_group_ids.filter((item) => item !== id) : [...form.age_group_ids, id]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError(null);
    const body = { ...form, calendar_plan_number: form.calendar_plan === "none" ? null : form.calendar_plan_number || null, end_date: form.end_date || form.date };
    try {
      if (editing) {
        const { status: _status, ...changes } = body;
        await api(`/competitions/${editing.id}`, json("PATCH", changes));
      } else {
        await api("/competitions", json("POST", body));
      }
      onSaved();
    } catch (reason) {
      setError(errorText(reason, "Не удалось сохранить"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <div className="form-wide card-heading">
        <h2>{editing ? "Редактирование соревнования" : "Новое соревнование"}</h2>
        {editing && <button type="button" className="link-button" onClick={onCancel}>Отменить</button>}
      </div>
      <label className="form-wide">Название<input required maxLength={255} value={form.title} onChange={(event) => set("title", event.target.value)} /></label>
      <label>Дисциплина
        <select value={form.discipline_id} onChange={(event) => set("discipline_id", Number(event.target.value))}>
          {reference.disciplines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label>Тип (из справочника)
        <select value={form.competition_type_id} onChange={(event) => set("competition_type_id", Number(event.target.value))}>
          {reference.competition_types.filter((item) => item.is_active || item.id === form.competition_type_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label>Статус соревнования
        <select value={form.level} onChange={(event) => {
          const level = event.target.value as CompetitionLevel;
          setForm((current) => ({ ...current, level, calendar_plan: current.calendar_plan === "none" ? "none" : expectedPlan(level) }));
        }}>
          {keys(levelLabels).map((item) => <option key={item} value={item}>{levelLabels[item]}</option>)}
        </select>
      </label>
      <label>Формат проведения
        <select value={form.format} onChange={(event) => set("format", event.target.value as CompetitionPayload["format"])}>
          {keys(formatLabels).map((item) => <option key={item} value={item}>{formatLabels[item]}</option>)}
        </select>
        {form.format === "mixed" && <small>Например: разработка онлайн, защита проектов очно.</small>}
      </label>
      <fieldset className="form-wide checks">
        <legend>Возрастные группы</legend>
        {reference.age_groups.map((item) => (
          <label key={item.id} className="checkbox"><input type="checkbox" checked={form.age_group_ids.includes(item.id)} onChange={() => toggleGroup(item.id)} /><span>{item.name}</span></label>
        ))}
      </fieldset>
      <label>Начало<input required type="date" value={form.date} onChange={(event) => set("date", event.target.value)} /></label>
      <label>Окончание<input type="date" min={form.date} value={form.end_date} onChange={(event) => set("end_date", event.target.value)} /><small>Пусто — однодневное.</small></label>
      <label>Приём заявок с<input required type="date" value={form.registration_start} onChange={(event) => set("registration_start", event.target.value)} /></label>
      <label>Приём заявок до<input required type="date" max={form.date} value={form.registration_end} onChange={(event) => set("registration_end", event.target.value)} /></label>
      <label className="form-wide">Место проведения<input required maxLength={255} value={form.location} onChange={(event) => set("location", event.target.value)} /></label>
      <label>Календарный план
        <select value={form.calendar_plan} onChange={(event) => set("calendar_plan", event.target.value as CalendarPlan)}>
          <option value="none">{planLabels.none}</option>
          <option value={expectedPlan(form.level)}>{planLabels[expectedPlan(form.level)]}</option>
        </select>
      </label>
      <label>Номер в плане<input maxLength={60} disabled={form.calendar_plan === "none"} value={form.calendar_plan_number ?? ""} onChange={(event) => set("calendar_plan_number", event.target.value)} placeholder="например, КП-2026/118" /></label>
      {!editing && (
        <label>Начальный этап
          <select value={form.status} onChange={(event) => set("status", event.target.value as CompetitionPayload["status"])}>
            {keys(statusLabels).map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
          </select>
        </label>
      )}
      <label className="form-wide">Описание<textarea required maxLength={5000} rows={4} value={form.description} onChange={(event) => set("description", event.target.value)} /></label>
      <FormError error={error} />
      <button className="button form-wide" disabled={saving || form.age_group_ids.length === 0}>{saving ? "Сохраняем…" : editing ? "Сохранить изменения" : "Создать соревнование"}</button>
    </form>
  );
}

function RegulationUpload({ item, onDone }: { item: Competition; onDone: (message: string | null, error: string | null) => void }) {
  async function upload(file: File | undefined) {
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    try {
      await api(`/competitions/${item.id}/regulation`, { method: "PUT", body });
      onDone(`Положение «${file.name}» опубликовано`, null);
    } catch (reason) { onDone(null, errorText(reason)); }
  }
  return (
    <label className="file-button">
      {item.regulation_filename ? "Заменить положение" : "Загрузить положение"}
      <input type="file" accept=".pdf,.doc,.docx" onChange={(event) => void upload(event.target.files?.[0])} />
    </label>
  );
}

function AdminCompetitions({ reference }: { reference: Reference }) {
  const [items, setItems] = useState<Competition[] | null>(null);
  const [editing, setEditing] = useState<Competition | null>(null);
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const reload = () => setVersion((value) => value + 1);

  useEffect(() => {
    api<Competition[]>("/competitions?include_archived=true").then(setItems).catch((reason) => setError(errorText(reason)));
  }, [version]);

  async function action(path: string, init: RequestInit, message: string) {
    setError(null); setNotice(null);
    try { await api(path, init); setNotice(message); reload(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <>
      <CompetitionForm key={editing?.id ?? "new"} reference={reference} editing={editing} onCancel={() => setEditing(null)}
        onSaved={() => { setNotice(editing ? "Изменения сохранены" : "Соревнование создано"); setEditing(null); reload(); }} />
      <div className="section-heading"><h2>Все соревнования</h2>{items && <span className="counter">{items.length}</span>}</div>
      <FormError error={error} /><Notice text={notice} />
      {!items && !error && <State code="…" title="Загружаем" text="Получаем список соревнований." />}
      {items?.length === 0 && <State code="00" title="Соревнований пока нет" text="Создайте первое с помощью формы выше." />}
      <div className="admin-list">
        {items?.map((item) => (
          <article className={`admin-row${item.is_archived ? " is-archived" : ""}`} key={item.id}>
            <div>
              <div className="event-tags"><StatusBadge status={item.status} /><span className="tag">{levelLabels[item.level]}</span>{item.is_archived && <span className="tag">Архив</span>}</div>
              <h3>{item.title}</h3>
              <p className="muted">{item.discipline.name} · {formatRange(item.date, item.end_date)} · {item.regulation_filename ? "положение опубликовано" : "без положения"}</p>
            </div>
            {!item.is_archived && (
              <div className="admin-actions">
                <button type="button" className="button button--small button--ghost" onClick={() => { setEditing(item); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Изменить</button>
                <select aria-label={`Этап: ${item.title}`} value={item.status} onChange={(event) => void action(`/competitions/${item.id}/status`, json("PATCH", { status: event.target.value }), "Этап обновлён")}>
                  {keys(statusLabels).map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
                </select>
                {item.status === "registration_open" && <button type="button" className="button button--small button--ghost" onClick={() => void action(`/competitions/${item.id}/close-registration`, { method: "POST" }, "Приём заявок закрыт")}>Закрыть приём</button>}
                <RegulationUpload item={item} onDone={(message, uploadError) => { setNotice(message); setError(uploadError); reload(); }} />
                <button type="button" className="link-button danger" onClick={() => { if (window.confirm(`Отправить «${item.title}» в архив?`)) void action(`/competitions/${item.id}/archive`, { method: "POST" }, "Перенесено в архив"); }}>В архив</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}

export function AdminCompetitionsPage() {
  const { reference } = useSession();
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Календарь соревнований" />
      <AdminGate>{reference ? <AdminCompetitions reference={reference} /> : <State code="…" title="Загружаем справочники" text="Подождите секунду." />}</AdminGate>
    </section>
  );
}
