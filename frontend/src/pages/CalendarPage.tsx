import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api, errorText } from "../shared/api";
import { formatLabels, formatRange, keys, levelLabels, statusLabels } from "../shared/labels";
import type { Competition } from "../shared/types";
import { State, StatusBadge } from "../shared/ui";

const FILTERS = ["discipline_id", "level", "age_group_id", "status"] as const;

export function CalendarPage() {
  const { reference } = useSession();
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<Competition[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const query = useMemo(() => {
    const search = new URLSearchParams();
    FILTERS.forEach((name) => { const value = params.get(name); if (value) search.set(name, value); });
    return search.toString();
  }, [params]);

  useEffect(() => {
    let active = true;
    setItems(null);
    setError(null);
    api<Competition[]>(`/competitions${query ? `?${query}` : ""}`)
      .then((data) => { if (active) setItems(data); })
      .catch((reason) => { if (active) setError(errorText(reason, "Не удалось загрузить календарь")); });
    return () => { active = false; };
  }, [query]);

  const setFilter = (name: (typeof FILTERS)[number], value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value); else next.delete(name);
    setParams(next, { replace: true });
  };
  const hasFilters = FILTERS.some((name) => params.get(name));

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Региональное отделение · Оренбургская область</span>
        <h1>Календарь соревнований по спортивному программированию</h1>
        <p>Шесть дисциплин вида спорта: от алгоритмического программирования до беспилотных авиационных систем. Выберите соревнование, скачайте положение и подайте заявку из личного кабинета.</p>
      </section>

      <section className="section" aria-labelledby="calendar-title">
        <div className="section-heading">
          <h2 id="calendar-title">События</h2>
          {items && <span className="counter">{String(items.length).padStart(2, "0")}</span>}
        </div>

        <form className="filters" onSubmit={(event) => event.preventDefault()}>
          <label>Дисциплина
            <select value={params.get("discipline_id") ?? ""} onChange={(event) => setFilter("discipline_id", event.target.value)}>
              <option value="">Все дисциплины</option>
              {reference?.disciplines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>Возрастная группа
            <select value={params.get("age_group_id") ?? ""} onChange={(event) => setFilter("age_group_id", event.target.value)}>
              <option value="">Все группы</option>
              {reference?.age_groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>Статус соревнования
            <select value={params.get("level") ?? ""} onChange={(event) => setFilter("level", event.target.value)}>
              <option value="">Любой</option>
              {keys(levelLabels).map((level) => <option key={level} value={level}>{levelLabels[level]}</option>)}
            </select>
          </label>
          <label>Этап
            <select value={params.get("status") ?? ""} onChange={(event) => setFilter("status", event.target.value)}>
              <option value="">Все этапы</option>
              {keys(statusLabels).filter((status) => status !== "draft").map((status) => <option key={status} value={status}>{statusLabels[status]}</option>)}
            </select>
          </label>
          {hasFilters && <button type="button" className="link-button" onClick={() => setParams({}, { replace: true })}>Сбросить фильтры</button>}
        </form>

        {!items && !error && <State code="…" title="Загружаем календарь" text="Получаем список соревнований." />}
        {error && <State code="ERR" title="Календарь недоступен" text={error} />}
        {items?.length === 0 && (
          <State code="00" title={hasFilters ? "По фильтрам ничего не найдено" : "Соревнований пока нет"}
            text={hasFilters ? "Измените условия поиска или сбросьте фильтры." : "Новые события появятся после публикации федерацией."} />
        )}
        {items && items.length > 0 && (
          <div className="event-list">
            {items.map((item) => (
              <Link className="event-card" to={`/competitions/${item.id}`} key={item.id}>
                <div className="event-tags">
                  <StatusBadge status={item.status} />
                  <span className="tag">{levelLabels[item.level]}</span>
                  <span className="tag">{item.competition_type.name}</span>
                </div>
                <strong className="event-title">{item.title}</strong>
                <span className="event-discipline">{item.discipline.name}</span>
                <dl className="event-meta">
                  <div><dt>Даты</dt><dd>{formatRange(item.date, item.end_date)}</dd></div>
                  <div><dt>Формат</dt><dd>{formatLabels[item.format]} · {item.location}</dd></div>
                  <div><dt>Возраст</dt><dd>{item.age_groups.map((group) => group.name).join(", ")}</dd></div>
                </dl>
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
