import { Fragment, useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useSession } from "../../app/session";
import { api, errorText, fileUrl, json } from "../../shared/api";
import { birthYear, formatDate, keys, levelLabels, rankLabels, sanctionLabels, todayIso } from "../../shared/labels";
import type { Rating, RatingSettings, RegistryRow, Sanction, SanctionKind, SportRank, Team } from "../../shared/types";
import { FormError, Notice, PageTitle, State } from "../../shared/ui";
import { AdminGate } from "./AdminGate";

type Filters = { discipline_id: string; season: string; age_group_id: string; min_rank: string };

function RatingTable({ rating, onTeamCreated }: { rating: Rating; onTeamCreated: () => void }) {
  const [open, setOpen] = useState<number | null>(null);
  const [selected, setSelected] = useState<Record<number, "main" | "reserve">>({});
  const [title, setTitle] = useState(`Сборная Оренбургской области: ${rating.discipline.name.toLowerCase()}, ${rating.season}`);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const chosen = Object.entries(selected);

  const toggle = (id: number) => setSelected((current) => {
    const next = { ...current };
    if (next[id]) delete next[id]; else next[id] = "main";
    return next;
  });

  async function createTeam(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try {
      await api("/teams", json("POST", {
        title, discipline_id: rating.discipline.id, season: rating.season, age_group_id: rating.age_group?.id ?? null,
        members: chosen.map(([id, kind]) => ({ athlete_id: Number(id), is_reserve: kind === "reserve" })),
      }));
      setSelected({});
      setNotice("Состав сформирован — скачайте список и проект приказа ниже");
      onTeamCreated();
    } catch (reason) { setError(errorText(reason)); }
  }

  if (rating.rows.length === 0) {
    return <State code="00" title="Рейтинг пуст" text="Нет результатов в опубликованных протоколах по этой дисциплине за сезон (или все отфильтрованы)." />;
  }

  return (
    <>
      <div className="table-wrap">
        <table className="protocol-table rating-table">
          <thead><tr><th>В сборную</th><th>Место</th><th>Спортсмен</th><th>Г. р.</th><th>Разряд</th><th>Баллы</th><th>Призовых</th><th>Коэф.</th><th>Итог</th><th /></tr></thead>
          <tbody>
            {rating.rows.map((row) => (
              <Fragment key={row.athlete.id}>
                <tr className={selected[row.athlete.id] ? "is-selected" : ""}>
                  <td>
                    <input type="checkbox" aria-label={`Включить ${row.athlete.full_name}`} checked={Boolean(selected[row.athlete.id])} onChange={() => toggle(row.athlete.id)} />
                    {selected[row.athlete.id] && (
                      <select aria-label="Состав" value={selected[row.athlete.id]} onChange={(event) => setSelected({ ...selected, [row.athlete.id]: event.target.value as "main" | "reserve" })}>
                        <option value="main">основной</option><option value="reserve">резерв</option>
                      </select>
                    )}
                  </td>
                  <td className="place">{row.place}</td>
                  <td>{row.athlete.full_name}<br /><small className="muted">{row.athlete.organization ?? "без организации"}</small></td>
                  <td>{birthYear(row.athlete.birth_date)}</td>
                  <td>{row.rank ? rankLabels[row.rank] : "—"}</td>
                  <td>{row.base_points}</td>
                  <td>{row.podiums}</td>
                  <td>×{row.coefficient}</td>
                  <td className="place">{row.total}</td>
                  <td><button type="button" className="link-button" onClick={() => setOpen(open === row.athlete.id ? null : row.athlete.id)}>{open === row.athlete.id ? "Скрыть" : "Расчёт"}</button></td>
                </tr>
                {open === row.athlete.id && (
                  <tr className="rating-detail">
                    <td colSpan={10}>
                      <ul className="mini-results">
                        {row.items.map((item) => (
                          <li key={item.competition_id}>{formatDate(item.date)} · {item.title} ({levelLabels[item.level].toLowerCase()}, {item.competition_type.toLowerCase()}) — {item.place} место → <strong>{item.points}</strong> {item.rule ? `по правилу «${item.rule}»` : "— правило для этого статуса не задано"}</li>
                        ))}
                      </ul>
                      <p className="muted">Сумма {row.base_points} × {row.coefficient} = {row.total}. Коэффициент стабильности ×{rating.settings.stability_coefficient} — при призовых местах на {rating.settings.stability_min_podiums} и более соревнованиях сезона.</p>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {rating.excluded.length > 0 && (
        <div className="excluded">
          <strong>Не попали в рейтинг:</strong>
          <ul>{rating.excluded.map((item) => <li key={item.athlete.id}>{item.athlete.full_name} — {item.reason}</li>)}</ul>
        </div>
      )}
      <form className="card team-form" onSubmit={createTeam}>
        <h2>Сформировать сборную · выбрано {chosen.length}</h2>
        <label>Название состава<input required minLength={3} maxLength={255} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
        <p className="muted">Отметьте спортсменов в таблице. Места и баллы рейтинга сохранятся в составе на момент формирования.</p>
        <FormError error={error} /><Notice text={notice} />
        <button className="button" disabled={chosen.length === 0}>Сформировать состав</button>
      </form>
    </>
  );
}

function Teams({ version }: { version: number }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<Team[]>("/teams").then(setTeams).catch((reason) => setError(errorText(reason))); }, []);
  useEffect(load, [load, version]);

  async function remove(team: Team) {
    if (!window.confirm(`Удалить состав «${team.title}»?`)) return;
    try { await api(`/teams/${team.id}`, { method: "DELETE" }); load(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card card--wide">
      <h2>Составы сборной</h2>
      {teams.length === 0 && <p className="muted">Составов пока нет — выберите спортсменов в рейтинге.</p>}
      <ul className="ref-list">
        {teams.map((team) => (
          <li key={team.id}>
            <span>{team.title}<br /><small className="muted">{team.discipline.name} · {team.season}{team.age_group ? ` · ${team.age_group.name}` : ""} · основных {team.members.filter((member) => !member.is_reserve).length}, резерв {team.members.filter((member) => member.is_reserve).length} · сформирован {formatDate(team.created_at)}</small></span>
            <span className="row-actions">
              <a className="button button--small" href={fileUrl(`/teams/${team.id}/list.docx`)}>Список .docx</a>
              <a className="button button--small button--ghost" href={fileUrl(`/teams/${team.id}/order.docx`)}>Проект приказа</a>
              <button type="button" className="link-button danger" onClick={() => void remove(team)}>Удалить</button>
            </span>
          </li>
        ))}
      </ul>
      <FormError error={error} />
    </section>
  );
}

function Sanctions({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<Sanction[]>([]);
  const [athletes, setAthletes] = useState<RegistryRow[]>([]);
  const [form, setForm] = useState({ athlete_id: "", kind: "suspension" as SanctionKind, starts_on: todayIso(), ends_on: "", reason: "" });
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<Sanction[]>("/sanctions").then(setItems).catch((reason) => setError(errorText(reason))); }, []);
  useEffect(() => { load(); api<RegistryRow[]>("/registry/athletes").then(setAthletes).catch(() => setAthletes([])); }, [load]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api("/sanctions", json("POST", { ...form, athlete_id: Number(form.athlete_id), ends_on: form.ends_on || null }));
      setForm({ ...form, athlete_id: "", reason: "" });
      load(); onChange();
    } catch (reason) { setError(errorText(reason)); }
  }
  async function remove(item: Sanction) {
    try { await api(`/sanctions/${item.id}`, { method: "DELETE" }); load(); onChange(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <section className="card card--wide">
      <h2>Дисквалификации и отстранения</h2>
      <p className="muted">Пока действует, спортсмен не попадает в рейтинг и в сборную.</p>
      <ul className="ref-list">
        {items.map((item) => (
          <li key={item.id}>
            <span>{item.athlete.full_name} — {sanctionLabels[item.kind].toLowerCase()} с {formatDate(item.starts_on)}{item.ends_on ? ` по ${formatDate(item.ends_on)}` : ", бессрочно"}<br /><small className="muted">{item.reason}</small></span>
            <span className="row-actions"><span className={`app-status app-status--${item.active ? "rejected" : "withdrawn"}`}>{item.active ? "действует" : "не действует"}</span><button type="button" className="link-button" onClick={() => void remove(item)}>Снять</button></span>
          </li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={submit}>
        <select required value={form.athlete_id} onChange={(event) => setForm({ ...form, athlete_id: event.target.value })}>
          <option value="">Спортсмен</option>
          {athletes.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
        </select>
        <select value={form.kind} onChange={(event) => setForm({ ...form, kind: event.target.value as SanctionKind })}>{keys(sanctionLabels).map((kind) => <option key={kind} value={kind}>{sanctionLabels[kind]}</option>)}</select>
        <input type="date" required aria-label="С" value={form.starts_on} onChange={(event) => setForm({ ...form, starts_on: event.target.value })} />
        <input type="date" aria-label="По" min={form.starts_on} value={form.ends_on} onChange={(event) => setForm({ ...form, ends_on: event.target.value })} />
        <input required minLength={3} maxLength={1000} placeholder="Основание (решение, рапорт)" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} />
        <button className="button button--small">Добавить</button>
      </form>
      <FormError error={error} />
    </section>
  );
}

function SettingsEditor({ onSaved }: { onSaved: () => void }) {
  const { reference } = useSession();
  const [settings, setSettings] = useState<RatingSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => { api<RatingSettings>("/rating/settings").then(setSettings).catch((reason) => setError(errorText(reason))); }, []);
  if (!settings) return <FormError error={error} />;

  const setRule = (index: number, patch: Partial<RatingSettings["points"][number]>) =>
    setSettings({ ...settings, points: settings.points.map((rule, position) => (position === index ? { ...rule, ...patch } : rule)) });

  async function save(event: FormEvent) {
    event.preventDefault();
    setError(null); setNotice(null);
    try { setSettings(await api<RatingSettings>("/rating/settings", json("PUT", settings))); setNotice("Настройки сохранены, рейтинг пересчитан"); onSaved(); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <form className="card card--wide" onSubmit={save}>
      <h2>Баллы рейтинга</h2>
      <p className="muted">Базовые значения из кейса; федерация может изменить их. Строка с конкретным типом соревнования точнее строки «любой тип».</p>
      <div className="table-wrap">
        <table className="protocol-table">
          <thead><tr><th>Название</th><th>Статус</th><th>Тип</th><th>1 место</th><th>2 место</th><th>3 место</th><th /></tr></thead>
          <tbody>
            {settings.points.map((rule, index) => (
              <tr key={index}>
                <td><input required value={rule.title} onChange={(event) => setRule(index, { title: event.target.value })} /></td>
                <td><select value={rule.level} onChange={(event) => setRule(index, { level: event.target.value as typeof rule.level })}>{keys(levelLabels).map((level) => <option key={level} value={level}>{levelLabels[level]}</option>)}</select></td>
                <td><select value={rule.competition_type_id ?? ""} onChange={(event) => setRule(index, { competition_type_id: event.target.value ? Number(event.target.value) : null })}>
                  <option value="">любой тип</option>{reference?.competition_types.map((type) => <option key={type.id} value={type.id}>{type.name}</option>)}
                </select></td>
                {(["first", "second", "third"] as const).map((place) => <td key={place}><input className="score-input" type="number" min={0} max={1000} required value={rule[place]} onChange={(event) => setRule(index, { [place]: Number(event.target.value) })} /></td>)}
                <td><button type="button" className="link-button danger" onClick={() => setSettings({ ...settings, points: settings.points.filter((_, position) => position !== index) })}>Убрать</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="inline-form">
        <button type="button" className="button button--small button--ghost" onClick={() => setSettings({ ...settings, points: [...settings.points, { title: "Новое правило", level: "all_russian", competition_type_id: null, first: 0, second: 0, third: 0 }] })}>+ Правило</button>
        <label className="inline-label">Коэффициент стабильности<input className="score-input" type="number" step="0.05" min={1} max={3} value={settings.stability_coefficient} onChange={(event) => setSettings({ ...settings, stability_coefficient: event.target.value })} /></label>
        <label className="inline-label">при призовых местах не меньше чем на<input className="score-input" type="number" min={1} max={20} value={settings.stability_min_podiums} onChange={(event) => setSettings({ ...settings, stability_min_podiums: Number(event.target.value) })} /></label>
      </div>
      <FormError error={error} /><Notice text={notice} />
      <button className="button">Сохранить настройки</button>
    </form>
  );
}

function RatingView() {
  const { reference } = useSession();
  const year = new Date().getFullYear();
  const [filters, setFilters] = useState<Filters>({ discipline_id: "1", season: String(year), age_group_id: "", min_rank: "" });
  const [rating, setRating] = useState<Rating | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const bump = () => setVersion((value) => value + 1);

  useEffect(() => {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    setError(null);
    api<Rating>(`/rating?${params}`).then(setRating).catch((reason) => setError(errorText(reason)));
  }, [filters, version]);

  const set = (name: keyof Filters) => (event: { target: { value: string } }) => setFilters({ ...filters, [name]: event.target.value });

  return (
    <div className="ref-grid">
      <section className="card card--wide">
        <form className="filters filters--rating" onSubmit={(event) => event.preventDefault()}>
          <label>Дисциплина<select value={filters.discipline_id} onChange={set("discipline_id")}>{reference?.disciplines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Сезон<select value={filters.season} onChange={set("season")}>{[year - 2, year - 1, year, year + 1].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label>Возрастная группа<select value={filters.age_group_id} onChange={set("age_group_id")}><option value="">Все</option>{reference?.age_groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label>Разряд не ниже<select value={filters.min_rank} onChange={set("min_rank")}><option value="">Любой</option>{keys(rankLabels).map((rank: SportRank) => <option key={rank} value={rank}>{rankLabels[rank]}</option>)}</select></label>
          <button type="button" className="link-button" onClick={() => setShowSettings(!showSettings)}>{showSettings ? "Скрыть настройки" : "Настройки баллов"}</button>
        </form>
        {error && <State code="ERR" title="Рейтинг не загрузился" text={error} />}
        {!rating && !error && <State code="…" title="Считаем рейтинг" text="Подождите секунду." />}
        {rating && <RatingTable key={`${filters.discipline_id}-${filters.season}-${filters.age_group_id}`} rating={rating} onTeamCreated={bump} />}
      </section>
      {showSettings && <SettingsEditor onSaved={bump} />}
      <Teams version={version} />
      <Sanctions onChange={bump} />
    </div>
  );
}

export function AdminRatingPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Кабинет федерации" title="Рейтинг и сборная">
        <p className="lead">Баллы за места в опубликованных протоколах сезона с учётом уровня соревнования; ×1,2 за стабильность. Расчёт по каждому спортсмену открыт.</p>
      </PageTitle>
      <AdminGate><RatingView /></AdminGate>
    </section>
  );
}
