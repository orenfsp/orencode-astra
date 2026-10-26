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

const API_URL = "http://127.0.0.1:8000/api/v1/competitions";

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
    day: "numeric",
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
    <main>
      <section className="hero">
        <div className="hero__content">
          <span className="eyebrow">Платформа ФСП</span>
          <h1>Соревнуйся. Развивайся. Побеждай.</h1>
          <p>
            Актуальные турниры Федерации спортивного программирования — в одном месте.
          </p>
        </div>
      </section>

      <section className="competitions" aria-labelledby="competitions-title">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Календарь</span>
            <h2 id="competitions-title">Ближайшие соревнования</h2>
          </div>
          {!isLoading && !error && competitions.length > 0 && (
            <span className="counter">{competitions.length} событий</span>
          )}
        </div>

        {isLoading && (
          <div className="state" role="status">
            <span className="loader" aria-hidden="true" />
            Загружаем соревнования…
          </div>
        )}

        {error && (
          <div className="state state--error" role="alert">
            <strong>Не удалось загрузить список</strong>
            <span>{error}. Проверьте, что API запущен.</span>
          </div>
        )}

        {!isLoading && !error && competitions.length === 0 && (
          <div className="state">Пока нет запланированных соревнований.</div>
        )}

        {!isLoading && !error && competitions.length > 0 && (
          <div className="competition-grid">
            {competitions.map((competition) => (
              <article className="competition-card" key={competition.id}>
                <div className="card-topline">
                  <span className="discipline">{competition.discipline}</span>
                  <span className={`status status--${competition.status}`}>
                    {statusLabels[competition.status] ?? competition.status}
                  </span>
                </div>
                <h3>{competition.title}</h3>
                <dl>
                  <div>
                    <dt>Дата</dt>
                    <dd>{formatDate(competition.date)}</dd>
                  </div>
                  <div>
                    <dt>Место</dt>
                    <dd>{competition.location}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
