import { useState } from "react";
import type { FormEvent } from "react";
import { useSession } from "../../app/session";
import { api, errorText, json } from "../../shared/api";
import { keys, organizationTypeLabels } from "../../shared/labels";
import type { OrganizationType, Reference } from "../../shared/types";
import { FormError, Notice, PageTitle, State } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

function useSubmit(onDone: () => Promise<void>) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  async function run(action: () => Promise<unknown>, message: string) {
    setError(null); setNotice(null);
    try { await action(); await onDone(); setNotice(message); return true; } catch (reason) { setError(errorText(reason)); return false; }
  }
  return { error, notice, run };
}

function CompetitionTypes({ reference, reload }: { reference: Reference; reload: () => Promise<void> }) {
  const [name, setName] = useState("");
  const { error, notice, run } = useSubmit(reload);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await run(() => api("/reference/competition-types", json("POST", { name })), `Тип «${name}» добавлен`)) setName("");
  }
  return (
    <section className="card">
      <h2>Типы соревнований</h2>
      <ul className="ref-list">
        {reference.competition_types.map((item) => (
          <li key={item.id} className={item.is_active ? "" : "is-muted"}>
            <span>{item.name}</span>
            <button type="button" className="link-button" onClick={() => void run(() => api(`/reference/competition-types/${item.id}`, json("PUT", { name: item.name, is_active: !item.is_active })), "Сохранено")}>
              {item.is_active ? "Скрыть" : "Вернуть"}
            </button>
          </li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={submit}>
        <input required minLength={2} maxLength={120} placeholder="Новый тип, например «Спартакиада»" value={name} onChange={(event) => setName(event.target.value)} />
        <button className="button button--small">Добавить</button>
      </form>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

function AgeGroups({ reference, reload }: { reference: Reference; reload: () => Promise<void> }) {
  const [form, setForm] = useState({ name: "", min_age: "", max_age: "" });
  const { error, notice, run } = useSubmit(reload);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = { name: form.name, min_age: Number(form.min_age), max_age: form.max_age ? Number(form.max_age) : null };
    if (await run(() => api("/reference/age-groups", json("POST", body)), "Возрастная группа добавлена")) setForm({ name: "", min_age: "", max_age: "" });
  }
  return (
    <section className="card">
      <h2>Возрастные группы</h2>
      <p className="muted">По правилам вида спорта (приказ Минспорта № 584). Используются для проверки заявок.</p>
      <ul className="ref-list">
        {reference.age_groups.map((item) => <li key={item.id}><span>{item.name}</span><span className="muted">{item.min_age}{item.max_age ? `–${item.max_age}` : "+"} лет</span></li>)}
      </ul>
      <form className="inline-form" onSubmit={submit}>
        <input required minLength={2} maxLength={120} placeholder="Название" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <input required type="number" min={5} max={100} placeholder="от" value={form.min_age} onChange={(event) => setForm({ ...form, min_age: event.target.value })} />
        <input type="number" min={5} max={100} placeholder="до" value={form.max_age} onChange={(event) => setForm({ ...form, max_age: event.target.value })} />
        <button className="button button--small">Добавить</button>
      </form>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

function Organizations({ reference, reload }: { reference: Reference; reload: () => Promise<void> }) {
  const [form, setForm] = useState({ name: "", org_type: "school" as OrganizationType, municipality_id: "" });
  const { error, notice, run } = useSubmit(reload);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = { ...form, municipality_id: form.municipality_id ? Number(form.municipality_id) : null };
    if (await run(() => api("/reference/organizations", json("POST", body)), "Организация добавлена")) setForm({ ...form, name: "" });
  }
  return (
    <section className="card card--wide">
      <h2>Организации</h2>
      {reference.organizations.length === 0 && <p className="muted">Организаций пока нет.</p>}
      <ul className="ref-list">
        {reference.organizations.map((item) => (
          <li key={item.id}><span>{item.name}</span><span className="muted">{organizationTypeLabels[item.org_type]}{item.municipality ? ` · ${item.municipality.name}` : ""}</span></li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={submit}>
        <input required minLength={2} maxLength={255} placeholder="Название организации" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <select value={form.org_type} onChange={(event) => setForm({ ...form, org_type: event.target.value as OrganizationType })}>
          {keys(organizationTypeLabels).map((item) => <option key={item} value={item}>{organizationTypeLabels[item]}</option>)}
        </select>
        <select value={form.municipality_id} onChange={(event) => setForm({ ...form, municipality_id: event.target.value })}>
          <option value="">Муниципалитет</option>
          {reference.municipalities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <button className="button button--small">Добавить</button>
      </form>
      <FormError error={error} /><Notice text={notice} />
    </section>
  );
}

export function AdminReferencePage() {
  const { reference, reloadReference } = useSession();
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Справочники" />
      <AdminGate>
        {!reference ? <State code="…" title="Загружаем справочники" text="Подождите секунду." /> : (
          <div className="ref-grid">
            <section className="card">
              <h2>Дисциплины</h2>
              <p className="muted">Шесть дисциплин вида спорта — фиксированный список.</p>
              <ol className="ref-list">{reference.disciplines.map((item) => <li key={item.id}><span>{item.name}</span></li>)}</ol>
            </section>
            <CompetitionTypes reference={reference} reload={reloadReference} />
            <AgeGroups reference={reference} reload={reloadReference} />
            <Organizations reference={reference} reload={reloadReference} />
          </div>
        )}
      </AdminGate>
    </section>
  );
}
