import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Competition = {
  id: number | string;
  title: string;
  discipline: string;
  date: string;
  location: string;
  status: string;
};

const API_URL = "http://127.0.0.1:8002/api/v1/competitions";

const statusLabels: Record<string, string> = {
  upcoming: "Скоро",
  registration_open: "Регистрация открыта",
  ongoing: "Идёт сейчас",
  completed: "Завершено",
};

function formatDate(value: string) {
  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(parsedDate);
}

function App() {
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadCompetitions() {
      try {
        const response = await fetch(API_URL, { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`Сервер ответил с кодом ${response.status}`);
        }

        const data: unknown = await response.json();

        if (!Array.isArray(data)) {
          throw new Error("Сервер вернул данные в неожиданном формате");
        }

        setCompetitions(data as Competition[]);
      } catch (requestError) {
        if (requestError instanceof DOMException && requestError.name === "AbortError") {
          return;
        }

        setError(
          requestError instanceof Error
            ? requestError.message
            : "Не удалось загрузить соревнования",
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadCompetitions();

    return () => controller.abort();
  }, []);

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-main page-width">
          <a className="brand" href="#top" aria-label="ФСП Оренбургская область">
            <span className="brand-mark" aria-hidden="true">
              <i /><i /><i /><i />
            </span>
            <span className="brand-short">ФСП</span>
            <span className="brand-region">Оренбургская<br />область</span>
          </a>
          <div className="header-meta">
            <span className="region-code">REG / 56</span>
            <span className="signal"><i /> Система работает</span>
          </div>
        </div>
        <div className="header-nav">
          <nav className="page-width" aria-label="Основная навигация">
            <a className="is-active" href="#competitions">Соревнования</a>
            <span>О федерации</span>
            <span>Дисциплины</span>
            <span>Оренбург · UTC+5</span>
          </nav>
        </div>
      </header>

      <main id="top">
        <section className="intro page-width" aria-labelledby="page-title">
          <div className="intro-copy">
            <span className="eyebrow">Региональный календарь / 2026</span>
            <h1 id="page-title">Спортивное<br />программирование</h1>
          </div>
          <p>
            Турниры, чемпионаты и открытые соревнования<br className="desktop-break" />
            Оренбургской области.
          </p>
        </section>

        <section className="competitions page-width" id="competitions" aria-labelledby="competitions-title">
          <div className="section-heading">
            <div>
              <span className="section-index">01</span>
              <h2 id="competitions-title">Ближайшие события</h2>
            </div>
            {!isLoading && !error && competitions.length > 0 && (
              <span className="counter">{String(competitions.length).padStart(2, "0")} / в календаре</span>
            )}
          </div>

          {isLoading && (
            <div className="state" role="status">
              <span className="loader" aria-hidden="true" />
              <div><strong>Получаем календарь</strong><span>Синхронизация с региональным API…</span></div>
            </div>
          )}

          {error && (
            <div className="state state--error" role="alert">
              <span className="state-code">ERR</span>
              <div><strong>Не удалось загрузить список</strong><span>{error}. Проверьте, что API запущен.</span></div>
            </div>
          )}

          {!isLoading && !error && competitions.length === 0 && (
            <div className="state">
              <span className="state-code">00</span>
              <div><strong>Событий пока нет</strong><span>Новые соревнования появятся здесь после публикации.</span></div>
            </div>
          )}

          {!isLoading && !error && competitions.length > 0 && (
            <div className="competition-list">
              {competitions.map((competition, index) => (
                <article className="competition-row" key={competition.id}>
                  <div className="row-number">{String(index + 1).padStart(2, "0")}</div>
                  <div className="competition-main">
                    <div className="card-topline">
                      <span className={`status status--${competition.status}`}>
                        <i aria-hidden="true" />
                        {statusLabels[competition.status] ?? competition.status}
                      </span>
                      <span className="discipline">{competition.discipline}</span>
                    </div>
                    <h3>{competition.title}</h3>
                  </div>
                  <dl>
                    <div>
                      <dt>Дата</dt>
                      <dd>{formatDate(competition.date)}</dd>
                    </div>
                    <div>
                      <dt>Формат / место</dt>
                      <dd>{competition.location}</dd>
                    </div>
                  </dl>
                  <span className="row-arrow" aria-hidden="true">↗</span>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="page-width">
        <span>ФСП / ОРЕНБУРГСКАЯ ОБЛАСТЬ</span>
        <span>КОД · СПОРТ · СООБЩЕСТВО</span>
      </footer>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode><App /></StrictMode>,
);
