import { Link } from "react-router-dom";
import { fileUrl } from "../shared/api";
import { PageTitle } from "../shared/ui";

const SOURCE = "https://sudact.ru/law/pravila-vida-sporta-sportivnoe-programmirovanie-utv-prikazom/prilozhenie-n-5";
const CRITERIA = ["Работоспособность прототипа", "Соответствие функциональным требованиям", "Презентация", "Технологичность", "Потенциал"];
const TASKS = Array.from({ length: 12 }, (_, index) => index + 1);

function TasksSample() {
  return (
    <div className="table-wrap">
      <table className="protocol-table protocol-table--form protocol-table--sample">
        <thead>
          <tr><th rowSpan={2}>N п/п</th><th rowSpan={2}>Наименование команды (состав)</th><th colSpan={12} className="center">Задачи</th><th rowSpan={2}>Решено</th><th rowSpan={2}>Время выполнения задач</th></tr>
          <tr>{TASKS.map((number) => <th key={number} className="center">{number}</th>)}</tr>
        </thead>
        <tbody>
          {[1, 2, 3].map((row) => <tr key={row}><td>{row}.</td><td />{TASKS.map((number) => <td key={number} />)}<td /><td /></tr>)}
        </tbody>
      </table>
    </div>
  );
}

function ProductSample() {
  return (
    <div className="table-wrap">
      <table className="protocol-table protocol-table--form protocol-table--sample">
        <thead>
          <tr><th>Фамилия, имя, отчество (при наличии) судьи</th><th>Команда (состав)</th>{CRITERIA.map((item) => <th key={item} className="center criterion">{item} (10%)</th>)}<th>ИТОГО</th></tr>
        </thead>
        <tbody>
          {["Судья 1", "Судья 2", "Судья 3", "ОБЩЕЕ"].map((label) => (
            <tr key={label} className={label === "ОБЩЕЕ" ? "overall" : ""}><td>{label === "ОБЩЕЕ" ? <strong>{label}</strong> : label}</td><td />{CRITERIA.map((item) => <td key={item} />)}<td /></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProtocolFormsPage() {
  return (
    <section className="section">
      <PageTitle eyebrow="Документы вида спорта" title="Образцы протоколов">
        <p className="lead">
          Протоколы на платформе формируются по рекомендуемым образцам из Приложения № 5 к Правилам вида спорта «спортивное программирование»,
          утверждённым приказом Минспорта России от 11.08.2023 № 584. Форма выбирается автоматически по дисциплине соревнования.
        </p>
      </PageTitle>

      <article className="card form-sample">
        <h2>Протокол по программированию алгоритмическому, робототехники, БАС и информационных систем безопасности</h2>
        <p>
          Для каждой команды (участника) по каждой задаче ставится отметка: «+» — решена с первой попытки, «+2» — решена после двух неудачных,
          «-1» — не решена, пусто — не сдавалась. «Решено» — число решённых задач, «Время выполнения задач» — суммарное время в минутах.
          Места распределяются по числу решённых задач, при равенстве — по меньшему времени. Внизу протокола — сколько задач предложено
          к решению, сколько команд решили все задачи и сколько не решили ни одной. На платформе по этой форме ведутся также соревнования
          по программированию систем искусственного интеллекта.
        </p>
        <TasksSample />
        <div className="detail-actions">
          <a className="button" href={fileUrl("/protocol-forms/tasks.docx")}>Скачать бланк .docx</a>
          <a className="button button--ghost" href={`${SOURCE}/rekomenduemyi-obrazets-protokola-po-programmirovaniiu/`} target="_blank" rel="noreferrer">Образец в тексте Правил ↗</a>
        </div>
      </article>

      <article className="card form-sample">
        <h2>Протокол по программированию продуктовому</h2>
        <p>
          Каждую команду оценивают три судьи по пяти критериям, у каждого критерия вес 10%. В строке судьи — его оценки и итог,
          в строке «ОБЩЕЕ» — среднее судей по каждому критерию и общий итог, по которому распределяются места.
        </p>
        <ProductSample />
        <div className="detail-actions">
          <a className="button" href={fileUrl("/protocol-forms/product.docx")}>Скачать бланк .docx</a>
          <a className="button button--ghost" href={`${SOURCE}/rekomenduemyi-obrazets-protokola-po-programmirovaniiu_1/`} target="_blank" rel="noreferrer">Образец в тексте Правил ↗</a>
        </div>
      </article>

      <p className="muted">
        Оба протокола подписывают главный судья и главный секретарь соревнований (подпись, инициалы и фамилия), ставятся дата и печать.
        Готовые протоколы прошедших соревнований — в <Link to="/">календаре</Link>, на странице соревнования.
      </p>
    </section>
  );
}
