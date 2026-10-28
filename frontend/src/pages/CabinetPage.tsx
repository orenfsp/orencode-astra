import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, errorText, fileUrl, json } from "../shared/api";
import { applicationStatusLabels, formatDate, genderLabels, keys, levelLabels, resultStatusLabels, roleLabels, stageLabels } from "../shared/labels";
import type { Application, Certificate, HistoryItem, MyProfile, Role } from "../shared/types";
import { FormError, GuestNotice, Notice, PageTitle, State } from "../shared/ui";
import { DeadlinesCard } from "../shared/widgets";
import { MyCoaches, MyRankCard } from "./cabinet/AthletePanels";
import { CoachPanel } from "./cabinet/CoachPanel";
import { JudgePanel } from "./cabinet/JudgePanel";

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
    end_year: athlete?.end_year ? String(athlete.end_year) : "",
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
        end_year: form.end_year ? Number(form.end_year) : null,
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
      <label>Прекратил занятия (год)<input type="number" min={1990} max={new Date().getFullYear()} placeholder="занимаюсь" value={form.end_year} onChange={set("end_year")} /><small>Нужно для отчёта о численности занимающихся.</small></label>
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
      <FormError error={error} /><Notice text={notice} />
      <button className="button form-wide">Сохранить</button>
    </form>
  );
}

function MyApplications() {
  const [items, setItems] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => { api<Application[]>("/me/applications").then(setItems).catch((reason) => setError(errorText(reason))); };
  useEffect(load, []);

  async function withdraw(item: Application) {
    if (!window.confirm(`Отозвать заявку на «${item.competition.title}»?`)) return;
    setError(null);
    try { await api(`/applications/${item.id}/withdraw`, { method: "POST" }); load(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card">
      <h2>Мои заявки</h2>
      {items?.length === 0 && <p className="muted">Заявок пока нет. Выберите соревнование в <Link to="/">календаре</Link> — платформа сама покажет, проходите ли вы по возрасту и дисциплине.</p>}
      <ul className="ref-list">
        {items?.map((item) => (
          <li key={item.id}>
            <span>
              <Link to={`/competitions/${item.competition.id}`}>{item.competition.title}</Link><br />
              <small className="muted">{formatDate(item.competition.date)} · {item.age_group.name}</small>
              {item.moderator_comment && <><br /><small className="muted">Комментарий федерации: {item.moderator_comment}</small></>}
            </span>
            <span className="row-actions">
              <span className={`app-status app-status--${item.status}`}>{applicationStatusLabels[item.status]}</span>
              {(item.status === "pending" || item.status === "approved") && !item.result && <button type="button" className="link-button" onClick={() => void withdraw(item)}>Отозвать</button>}
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} />
    </section>
  );
}

function MyResults() {
  const [items, setItems] = useState<HistoryItem[] | null>(null);
  const [certificates, setCertificates] = useState<Certificate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const loadCertificates = () => { api<Certificate[]>("/me/certificates").then(setCertificates).catch(() => setCertificates([])); };
  useEffect(() => { api<HistoryItem[]>("/me/results").then(setItems).catch(() => setItems([])); loadCertificates(); }, []);

  async function issue(item: HistoryItem) {
    const purpose = window.prompt("Для чего справка? (например, для поступления, для стипендии) — можно оставить пустым", "") ;
    if (purpose === null) return;
    setError(null);
    try {
      const certificate = await api<Certificate>("/me/certificates", json("POST", { application_id: item.application_id, purpose: purpose || null }));
      loadCertificates();
      window.location.href = fileUrl(`/certificates/${certificate.id}.docx`);
    } catch (reason) { setError(errorText(reason)); }
  }
  return (
    <section className="card">
      <h2>История выступлений</h2>
      {items?.length === 0 && <p className="muted">Результаты появятся здесь после публикации протокола соревнования.</p>}
      {items && items.length > 0 && <p><a className="button button--small button--ghost" href={fileUrl("/me/report.docx")}>Скачать отчёт о выступлениях .docx</a></p>}
      {items && items.length > 0 && (
        <div className="table-wrap">
          <table className="protocol-table">
            <thead><tr><th>Соревнование</th><th>Статус</th><th>Место</th><th>Баллы</th><th /></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.competition.id}>
                  <td>{item.competition.title}<br /><small className="muted">{item.competition.discipline.name} · {formatDate(item.competition.date)} · {item.age_group.name}</small></td>
                  <td>{levelLabels[item.competition.level]}</td>
                  <td className="place">{item.place ? `${item.place} из ${item.participants}` : resultStatusLabels[item.result_status]}</td>
                  <td>{item.score ?? "—"}</td>
                  <td className="row-actions start"><Link to={`/competitions/${item.competition.id}/protocol`}>Протокол</Link>{item.result_status === "ok" && <button type="button" className="link-button" onClick={() => void issue(item)}>Справка с QR</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <FormError error={error} />
      {certificates.length > 0 && (
        <details>
          <summary className="muted">Выданные справки ({certificates.length})</summary>
          <ul className="ref-list">
            {certificates.map((item) => (
              <li key={item.id}>
                <span>№ {item.number} · {item.competition.title}<br /><small className="muted">{formatDate(item.issued_at)}{item.purpose ? ` · ${item.purpose}` : ""}</small></span>
                <span className="row-actions"><a className="link-button" href={fileUrl(`/certificates/${item.id}.docx`)}>.docx</a><Link className="link-button" to={`/verify/${item.code}`}>Проверка</Link></span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function EmailSettings() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<{ email_notifications: boolean }>("/me/settings").then((data) => setEnabled(data.email_notifications)).catch(() => setEnabled(null)); }, []);
  if (enabled === null) return null;

  async function toggle(value: boolean) {
    setError(null);
    try { setEnabled((await api<{ email_notifications: boolean }>("/me/settings", json("PUT", { email_notifications: value }))).email_notifications); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card">
      <h2>Уведомления</h2>
      <label className="checkbox"><input type="checkbox" checked={enabled} onChange={(event) => void toggle(event.target.checked)} /><span>Дублировать уведомления на email</span></label>
      <p className="muted">В кабинете уведомления приходят всегда: <Link to="/notifications">все уведомления</Link>.</p>
      <FormError error={error} />
    </section>
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
          <DeadlinesCard role={user.active_role} />
          {user.active_role === "federation_admin" && (
            <section className="card">
              <h2>Федерация</h2>
              <p className="muted">Дашборд, календарь, разряды, судьи и справочники.</p>
              <div className="role-add"><Link className="button button--small" to="/admin">Открыть дашборд</Link></div>
            </section>
          )}
          <EmailSettings />
        </div>
        <div className="stack">
          {error && <State code="ERR" title="Профиль не загрузился" text={error} />}
          {user.active_role === "athlete" && <MyApplications />}
          {user.active_role === "athlete" && <MyResults />}
          {user.active_role === "athlete" && <MyRankCard />}
          {user.active_role === "athlete" && <MyCoaches />}
          {user.active_role === "coach" && <CoachPanel />}
          {user.active_role === "judge" && <JudgePanel />}
          {data && <ProfileForm key={`p-${data.profile?.last_name}`} data={data} onSaved={setData} />}
          {data && user.active_role === "athlete" && <AthleteForm key={`a-${data.profile?.birth_date}`} data={data} onSaved={setData} />}
          {data && user.active_role === "coach" && <CoachForm data={data} onSaved={setData} />}
        </div>
      </div>
    </section>
  );
}
