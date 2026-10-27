import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, errorText, json } from "../shared/api";
import { formatDate, genderLabels, keys, roleLabels, stageLabels } from "../shared/labels";
import type { MyProfile, Role } from "../shared/types";
import { FormError, GuestNotice, Notice, PageTitle, State } from "../shared/ui";

const PUBLIC_ROLES: Role[] = ["athlete", "coach", "judge"];

function RolesCard() {
  const { user, addRole, switchRole } = useSession();
  const [error, setError] = useState<string | null>(null);
  if (!user) return null;
  const missing = PUBLIC_ROLES.filter((role) => !user.roles.includes(role));

  async function run(action: () => Promise<void>) {
    setError(null);
    try { await action(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card">
      <h2>Роли аккаунта</h2>
      <p className="muted">Права проверяются по активной роли. Переключение не требует повторного входа.</p>
      <div className="role-list">
        {user.roles.map((role) => (
          <button key={role} type="button" className={`role-chip${role === user.active_role ? " is-active" : ""}`} aria-pressed={role === user.active_role} onClick={() => void run(() => switchRole(role))}>
            {roleLabels[role]}{role === user.active_role && " · активна"}
          </button>
        ))}
      </div>
      {missing.length > 0 && (
        <div className="role-add">
          <span className="muted">Добавить роль:</span>
          {missing.map((role) => <button key={role} type="button" className="link-button" onClick={() => void run(() => addRole(role))}>+ {roleLabels[role]}</button>)}
        </div>
      )}
      <FormError error={error} />
    </section>
  );
}

function ProfileForm({ data, onSaved }: { data: MyProfile; onSaved: (data: MyProfile) => void }) {
  const { reference } = useSession();
  const profile = data.profile;
  const [form, setForm] = useState({
    last_name: profile?.last_name ?? "", first_name: profile?.first_name ?? "", middle_name: profile?.middle_name ?? "",
    birth_date: profile?.birth_date ?? "", gender: profile?.gender ?? "", municipality_id: profile?.municipality?.id ? String(profile.municipality.id) : "",
    phone: profile?.phone ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const set = (name: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [name]: event.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try {
      onSaved(await api<MyProfile>("/me/profile", json("PUT", {
        ...form,
        middle_name: form.middle_name || null, birth_date: form.birth_date || null, gender: form.gender || null,
        municipality_id: form.municipality_id ? Number(form.municipality_id) : null, phone: form.phone || null,
      })));
      setNotice("Профиль сохранён");
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="form-wide">Личные данные</h2>
      <label>Фамилия<input required maxLength={120} value={form.last_name} onChange={set("last_name")} /></label>
      <label>Имя<input required maxLength={120} value={form.first_name} onChange={set("first_name")} /></label>
      <label>Отчество<input maxLength={120} value={form.middle_name} onChange={set("middle_name")} /></label>
      <label>Дата рождения<input type="date" value={form.birth_date} onChange={set("birth_date")} />
        <small>Нужна для проверки возрастной группы при заявке.</small>
      </label>
      <label>Пол<select value={form.gender} onChange={set("gender")}><option value="">Не указан</option>{keys(genderLabels).map((item) => <option key={item} value={item}>{genderLabels[item]}</option>)}</select></label>
      <label>Муниципалитет<select value={form.municipality_id} onChange={set("municipality_id")}><option value="">Не указан</option>{reference?.municipalities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      <label>Телефон<input type="tel" maxLength={40} value={form.phone} onChange={set("phone")} /></label>
      <FormError error={error} /><Notice text={notice} />
      <button className="button form-wide">Сохранить профиль</button>
    </form>
  );
}

function AthleteForm({ data, onSaved }: { data: MyProfile; onSaved: (data: MyProfile) => void }) {
  const { reference } = useSession();
  const athlete = data.athlete;
  const [form, setForm] = useState({
    organization_id: athlete?.organization?.id ? String(athlete.organization.id) : "",
    discipline_ids: athlete?.disciplines.map((item) => item.id) ?? [],
    start_year: athlete?.start_year ? String(athlete.start_year) : "",
    training_stage: athlete?.training_stage ?? "",
    guardian_name: athlete?.guardian_name ?? "", guardian_phone: athlete?.guardian_phone ?? "",
    guardian_consent: Boolean(athlete?.guardian_consent_at),
    rusada_completed_on: athlete?.rusada_completed_on ?? "", rusada_certificate_url: athlete?.rusada_certificate_url ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const set = (name: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [name]: event.target.value });
  const toggleDiscipline = (id: number) => setForm({
    ...form,
    discipline_ids: form.discipline_ids.includes(id) ? form.discipline_ids.filter((item) => item !== id) : [...form.discipline_ids, id],
  });

  if (!data.profile?.birth_date) {
    return <State code="01" title="Сначала укажите дату рождения" text="По ней платформа определяет возрастную группу и нужен ли законный представитель." />;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try {
      onSaved(await api<MyProfile>("/me/athlete", json("PUT", {
        organization_id: form.organization_id ? Number(form.organization_id) : null,
        discipline_ids: form.discipline_ids,
        start_year: form.start_year ? Number(form.start_year) : null,
        training_stage: form.training_stage || null,
        guardian_name: form.guardian_name || null, guardian_phone: form.guardian_phone || null, guardian_consent: form.guardian_consent,
        rusada_completed_on: form.rusada_completed_on || null, rusada_certificate_url: form.rusada_certificate_url || null,
      })));
      setNotice("Данные спортсмена сохранены");
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="form-wide">Спортсмен</h2>
      <fieldset className="form-wide checks">
        <legend>Дисциплины</legend>
        {reference?.disciplines.map((item) => (
          <label key={item.id} className="checkbox"><input type="checkbox" checked={form.discipline_ids.includes(item.id)} onChange={() => toggleDiscipline(item.id)} /><span>{item.name}</span></label>
        ))}
      </fieldset>
      <label>Организация
        <select value={form.organization_id} onChange={set("organization_id")}>
          <option value="">Без организации</option>
          {reference?.organizations.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <label>Год начала занятий<input type="number" min={1990} max={new Date().getFullYear()} value={form.start_year} onChange={set("start_year")} /></label>
      <label className="form-wide">Этап спортивной подготовки
        <select value={form.training_stage} onChange={set("training_stage")}><option value="">Не определён</option>{keys(stageLabels).map((item) => <option key={item} value={item}>{stageLabels[item]}</option>)}</select>
      </label>

      {data.is_minor && (
        <fieldset className="form-wide guardian">
          <legend>Законный представитель · спортсмену {data.age} лет</legend>
          <label>ФИО представителя<input required maxLength={255} value={form.guardian_name} onChange={set("guardian_name")} /></label>
          <label>Телефон представителя<input required type="tel" maxLength={40} value={form.guardian_phone} onChange={set("guardian_phone")} /></label>
          <label className="checkbox form-wide">
            <input type="checkbox" checked={form.guardian_consent} disabled={Boolean(athlete?.guardian_consent_at)} onChange={(event) => setForm({ ...form, guardian_consent: event.target.checked })} />
            <span>{athlete?.guardian_consent_at ? `Согласие представителя получено ${formatDate(athlete.guardian_consent_at)}` : "Законный представитель даёт согласие на обработку персональных данных несовершеннолетнего"}</span>
          </label>
        </fieldset>
      )}

      <fieldset className="form-wide">
        <legend>Антидопинг</legend>
        <p className="muted">Пройдите онлайн-курс РУСАДА и прикрепите ссылку на сертификат. Актуальные правила — на <a href="https://rusada.ru" target="_blank" rel="noreferrer">rusada.ru</a>.</p>
        <div className="form-grid inner">
          <label>Дата прохождения курса<input type="date" value={form.rusada_completed_on} onChange={set("rusada_completed_on")} /></label>
          <label>Ссылка на сертификат<input type="url" placeholder="https://" value={form.rusada_certificate_url} onChange={set("rusada_certificate_url")} /></label>
        </div>
      </fieldset>
      <FormError error={error} /><Notice text={notice} />
      <button className="button form-wide" disabled={form.discipline_ids.length === 0}>Сохранить данные спортсмена</button>
    </form>
  );
}

function CoachForm({ data, onSaved }: { data: MyProfile; onSaved: (data: MyProfile) => void }) {
  const { reference } = useSession();
  const [organizationId, setOrganizationId] = useState(data.coach?.organization?.id ? String(data.coach.organization.id) : "");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try {
      onSaved(await api<MyProfile>("/me/coach", json("PUT", { organization_id: organizationId ? Number(organizationId) : null })));
      setNotice("Данные тренера сохранены");
    } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <form className="card form-grid" onSubmit={submit}>
      <h2 className="form-wide">Тренер</h2>
      <label className="form-wide">Организация
        <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
          <option value="">Без организации</option>
          {reference?.organizations.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <p className="muted form-wide">Привязка спортсменов и заявки за них появятся на следующем этапе.</p>
      <FormError error={error} /><Notice text={notice} />
      <button className="button form-wide">Сохранить</button>
    </form>
  );
}

export function CabinetPage() {
  const { user } = useSession();
  const [data, setData] = useState<MyProfile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    api<MyProfile>("/me/profile").then(setData).catch((reason) => setError(errorText(reason)));
  }, [user]);

  if (user === undefined) return <section className="section"><State code="…" title="Проверяем сессию" text="Подождите секунду." /></section>;
  if (user === null) return <section className="section"><GuestNotice text="Личный кабинет доступен после входа." /></section>;

  return (
    <section className="section">
      <PageTitle eyebrow={`Кабинет · ${roleLabels[user.active_role]}`} title={user.full_name ?? user.email}>
        <p className="lead">{user.email}{data?.age != null && ` · ${data.age} лет`}</p>
      </PageTitle>
      <div className="cabinet-grid">
        <div className="stack">
          <RolesCard />
          {user.active_role === "federation_admin" && (
            <section className="card">
              <h2>Федерация</h2>
              <p className="muted">Управление календарём и справочниками.</p>
              <div className="role-add"><Link className="button button--small" to="/admin/competitions">Соревнования</Link><Link className="button button--small button--ghost" to="/admin/reference">Справочники</Link></div>
            </section>
          )}
          {user.active_role === "judge" && <State code="03" title="Кабинет судьи" text="Категория, назначения и заявки на категорию появятся на следующем этапе." />}
        </div>
        <div className="stack">
          {error && <State code="ERR" title="Профиль не загрузился" text={error} />}
          {data && <ProfileForm key={`p-${data.profile?.last_name}`} data={data} onSaved={setData} />}
          {data && user.active_role === "athlete" && <AthleteForm key={`a-${data.profile?.birth_date}`} data={data} onSaved={setData} />}
          {data && user.active_role === "coach" && <CoachForm data={data} onSaved={setData} />}
        </div>
      </div>
    </section>
  );
}
