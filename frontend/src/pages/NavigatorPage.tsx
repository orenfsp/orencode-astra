import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import { formatDate, organizationTypeLabels } from "../shared/labels";
import type { Competition } from "../shared/types";
import { StatusBadge } from "../shared/ui";

const DISCIPLINES: Record<string, string> = {
  algorithmic: "Олимпиадные задачи на алгоритмы и структуры данных: нужно придумать и запрограммировать решение за ограниченное время.",
  product: "Командная разработка цифрового продукта по заданию: от идеи и прототипа до защиты решения перед жюри.",
  security: "Соревнования по информационной безопасности (CTF): поиск уязвимостей, защита своих сервисов и атака чужих.",
  ai: "Анализ данных и машинное обучение: команды строят модели, которые решают прикладные задачи точнее соперников.",
  robotics: "Программирование роботов, которые автономно проходят трассу и выполняют задания на полигоне.",
  uav: "Программирование беспилотных авиационных систем: автономные полётные миссии, навигация, распознавание объектов.",
};

const STEPS = [
  ["Выберите дисциплину", "Ниже — шесть дисциплин вида спорта. Можно заниматься несколькими."],
  ["Найдите, где заниматься", "Школы, вузы, колледжи, спортивные школы и клубы области — в списке ниже. Можно заниматься и самостоятельно."],
  ["Зарегистрируйтесь на платформе", "Один аккаунт для спортсмена, тренера и судьи. Для несовершеннолетнего нужно согласие родителя или законного представителя."],
  ["Заполните профиль спортсмена", "Дата рождения и дисциплины нужны, чтобы платформа сама показывала, на какие соревнования вы проходите по возрасту."],
  ["Подайте заявку на соревнование", "Сами или через тренера. После соревнования результат появится в истории выступлений, а справку об участии можно скачать с QR-кодом."],
];

const GLOSSARY: [string, string][] = [
  ["Спортивный разряд", "Квалификация спортсмена по Единой всероссийской спортивной классификации (ЕВСК): юношеские разряды, 3, 2 и 1 спортивный разряд, кандидат в мастера спорта. Разряд присваивается за результат на официальных соревнованиях и действует ограниченный срок — его нужно подтверждать."],
  ["Статус соревнования", "Региональное (в пределах области), межрегиональное (несколько регионов, в том числе окружные) или всероссийское. От статуса зависят разряды и баллы рейтинга."],
  ["Чемпионат и первенство", "Чемпионат — соревнование среди взрослых спортсменов. Первенство — среди возрастных групп: мальчиков и девочек, юношей и девушек, юниоров."],
  ["Календарный план", "Официальные соревнования включаются в календарный план: региональные — в план Оренбургской области, межрегиональные и всероссийские — в Единый календарный план Минспорта России (ЕКП)."],
  ["Сборная области", "Формируется федерацией по рейтингу спортсменов за сезон: учитываются места на официальных соревнованиях и их уровень."],
  ["Антидопинг", "Каждый спортсмен проходит онлайн-курс РУСАДА и отмечает это в профиле. Актуальные правила и курс — на сайте rusada.ru."],
];

export function NavigatorPage() {
  const { reference, user } = useSession();
  const [events, setEvents] = useState<Competition[]>([]);

  useEffect(() => {
    api<Competition[]>("/competitions").then((items) => {
      const today = new Date().toISOString().slice(0, 10);
      setEvents(items.filter((item) => item.date >= today && ["registration_open", "upcoming"].includes(item.status)).slice(0, 4));
    }).catch(() => setEvents([]));
  }, []);

  const places = useMemo(() => {
    const groups = new Map<string, { name: string; type: string }[]>();
    for (const org of reference?.organizations.filter((item) => item.is_active) ?? []) {
      const key = org.municipality?.name ?? "Другие";
      groups.set(key, [...(groups.get(key) ?? []), { name: org.name, type: organizationTypeLabels[org.org_type] }]);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, "ru"));
  }, [reference]);

  return (
    <>
      <section className="hero">
        <span className="eyebrow">Навигатор для новичка</span>
        <h1>Спортивное программирование — с чего начать</h1>
        <p>Спортивное программирование — официальный вид спорта: здесь соревнуются в решении задач, разработке продуктов, кибербезопасности, искусственном интеллекте, робототехнике и программировании беспилотников. В Оренбургской области его развивает региональное отделение Федерации спортивного программирования.</p>
        {!user && <p><Link className="button" to="/login">Зарегистрироваться</Link></p>}
      </section>

      <section className="section">
        <div className="section-heading"><h2>Пять шагов</h2></div>
        <ol className="steps">
          {STEPS.map(([title, text], index) => <li key={title}><span className="step-number">{index + 1}</span><div><strong>{title}</strong><p className="muted">{text}</p></div></li>)}
        </ol>
      </section>

      <section className="section">
        <div className="section-heading"><h2>Дисциплины</h2><span className="counter">06</span></div>
        <div className="event-list">
          {reference?.disciplines.map((item) => (
            <Link key={item.id} className="event-card" to={`/?discipline_id=${item.id}`}>
              <strong className="event-title">{item.name}</strong>
              <span className="muted">{DISCIPLINES[item.code]}</span>
              <span className="event-discipline">Соревнования по дисциплине →</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading"><h2>Где заниматься в области</h2></div>
        <div className="ref-grid">
          {places.map(([municipality, orgs]) => (
            <section key={municipality} className="card">
              <h2>{municipality}</h2>
              <ul className="ref-list">{orgs.map((org) => <li key={org.name}><span>{org.name}</span><span className="muted">{org.type}</span></li>)}</ul>
            </section>
          ))}
        </div>
      </section>

      <section className="section">
        <div className="section-heading"><h2>Ближайшие соревнования</h2><Link className="link-button" to="/">Весь календарь</Link></div>
        {events.length === 0 && <p className="muted">Скоро здесь появятся новые события.</p>}
        <ul className="ref-list">
          {events.map((item) => (
            <li key={item.id}>
              <span><Link to={`/competitions/${item.id}`}>{item.title}</Link><br /><small className="muted">{formatDate(item.date)} · {item.discipline.name} · {item.age_groups.map((group) => group.name).join(", ")}</small></span>
              <StatusBadge status={item.status} />
            </li>
          ))}
        </ul>
      </section>

      <section className="section">
        <div className="section-heading"><h2>Справочник понятий</h2></div>
        <dl className="glossary">
          {GLOSSARY.map(([term, text]) => <div key={term}><dt>{term}</dt><dd>{text}</dd></div>)}
        </dl>
        <p className="muted">Тренерам и судьям: зарегистрируйтесь и добавьте себе роль в кабинете. Тренер привязывает спортсменов и подаёт за них заявки; судья получает назначения в судейские коллегии и подаёт заявку на судейскую категорию. Организациям, которые хотят вести спортивную подготовку, — пишите в федерацию: организация появится в реестре.</p>
      </section>
    </>
  );
}
