# Модель данных и API

## Модель данных

- `users`, `roles`, `user_roles`, `auth_sessions` — аккаунт, назначенные роли, сессии с активной ролью; `users.pd_consent_at` — согласие на обработку ПД.
- `profiles` — общие данные человека (ФИО, дата рождения, пол, муниципалитет).
- `athlete_profiles` + `athlete_disciplines` — данные спортсмена, дисциплины, организация (NULL — «без организации»), законный представитель, РУСАДА.
- `coach_profiles` — данные тренера.
- Справочники: `disciplines`, `competition_types`, `age_groups`, `municipalities`, `organizations`, `judge_positions`.
- `competitions` + `competition_age_groups` — соревнование со ссылками на справочники, уровень, формат, календарный план и номер, файл положения, число задач к решению (`task_count`), время публикации протокола. Форма протокола (`protocol_form`) определяется дисциплиной: продуктовое — оценки судей, остальные — задачи.
- `applications` — заявка спортсмена: соревнование, возрастная группа, кто и из какой роли подал, статус (на модерации / одобрена / отклонена / отозвана), решение федерации. Одна заявка на спортсмена в соревновании.
- `results` — результат по одобренной заявке: баллы, итог (результат / не явился / дисквалифицирован), рассчитанное место; для протокола по задачам — отметки по каждой задаче (`task_marks`) и время выполнения (`penalty_minutes`), для продуктового программирования — оценки судей по пяти критериям (`judge_scores`).
- `coach_links` + `coach_link_events` — связь тренер — спортсмен по дисциплине со статусом и историей изменений.
- `judge_profiles`, `judge_category_requests`, `judge_assignments` — категория судьи со сроком и приказом, заявки на категорию, назначения в судейские коллегии с должностью.
- `rank_requests`, `athlete_ranks`, `rank_norms` — заявки на разряд с результатом-основанием, присвоенные разряды (дата, приказ, срок), ориентиры ЕВСК для подсветки кандидатов.
- `rating_points`, `rating_settings` — баллы рейтинга по уровню и типу соревнования, коэффициент стабильности.
- `sanctions` — дисквалификации и отстранения со сроками.
- `teams` + `team_members` — составы сборной с основным составом и резервом, снимок места и баллов рейтинга.
- `athlete_profiles.end_year` — год прекращения занятий для динамики численности.
- `certificates` — справки об участии: номер, случайный код для QR и проверки, результат-основание.
- `indicator_documents` — подтверждающие документы к показателям развития по годам.
- `audit_log` — журнал действий: время, автор, активная роль, действие, сущность, изменённые поля (было → стало).
- `notifications` — уведомления в кабинете, отметка о прочтении и отправке на email; `users.email_notifications` — настройка внешнего канала.

Правило календарных планов проверяется на сервере: региональные соревнования включаются в план Оренбургской области, межрегиональные и всероссийские — в ЕКП Минспорта России.

## API

Все маршруты — под `/api/v1`, полная схема — в OpenAPI (`/docs`).

| Метод и путь | Доступ | Назначение |
| --- | --- | --- |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | — | Аккаунт и сессия |
| `POST /auth/role` | вход + CSRF | Переключить активную роль |
| `POST /auth/roles` | вход + CSRF | Добавить себе роль спортсмена, тренера или судьи |
| `GET /reference` | публично | Все справочники одним запросом |
| `POST/PUT /reference/competition-types`, `/age-groups`, `/organizations` | федерация | Пополнение справочников |
| `GET /me/profile`, `PUT /me/profile` | вход | Личные данные |
| `PUT /me/athlete`, `PUT /me/coach` | активная роль | Данные спортсмена и тренера |
| `GET /competitions`, `GET /competitions/{id}` | публично | Календарь с фильтрами `discipline_id`, `level`, `age_group_id`, `calendar_plan`, `status`, `q` |
| `POST /competitions`, `PATCH /competitions/{id}`, `PATCH /competitions/{id}/status`, `POST /competitions/{id}/close-registration`, `POST /competitions/{id}/archive` | федерация | Управление календарём |
| `PUT /competitions/{id}/regulation`, `GET /competitions/{id}/regulation` | федерация / публично | Положение соревнования |
| `GET /competitions/{id}/eligibility` | вход | Проходит ли спортсмен по возрасту и дисциплине, в какую группу |
| `POST /competitions/{id}/applications` | спортсмен | Подать заявку |
| `GET /me/applications`, `POST /applications/{id}/withdraw` | спортсмен | Мои заявки, отзыв |
| `GET /me/results` | спортсмен | История выступлений |
| `GET /competitions/{id}/applications`, `POST /applications/{id}/decision` | федерация | Модерация заявок |
| `PUT /competitions/{id}/results` | федерация | Внести или исправить результаты (отметки по задачам и время, оценки судей или баллы), места пересчитываются |
| `GET /competitions/{id}/protocol` | публично после публикации | Протокол по возрастным группам |
| `POST /competitions/{id}/protocol/publish`, `/unpublish` | федерация | Публикация протокола |
| `GET /coach/athletes/search`, `GET/POST /coach/links`, `POST /coach/links/{id}/status` | тренер | Поиск в реестре, запрос на привязку, смена статуса связи |
| `GET /me/coach-links`, `POST /me/coach-links/{id}/respond` | спортсмен | Подтвердить или отклонить тренера |
| `GET /coach/athletes`, `GET /coach/applications`, `GET /coach/rank-requests` | тренер | Сводка по подопечным |
| `GET /me/judge`, `POST /me/judge/requests` | судья | Категория, назначения, заявка на категорию |
| `GET /judges`, `GET /judge-requests`, `POST /judge-requests/{id}/decision` | федерация | Реестр судей, решения по категориям |
| `GET/POST /competitions/{id}/judges`, `DELETE /competitions/{id}/judges/{assignment_id}` | федерация | Судейская коллегия |
| `GET /me/rank`, `POST /rank-requests` | спортсмен / тренер | Разряд и заявка на разряд |
| `GET /rank-requests`, `POST /rank-requests/{id}/decision`, `GET /rank-candidates`, `GET /ranks/expiring`, `GET/PUT /rank-norms` | федерация | Разряды, кандидаты по ЕВСК, истекающие |
| `GET /me/deadlines` | вход | Сроки для активной роли |
| `GET /admin/dashboard`, `POST /admin/reminders/run` | федерация | Дашборд, запуск напоминаний |
| `GET /rating`, `GET/PUT /rating/settings` | федерация | Рейтинг с расчётом, настройки баллов |
| `GET/POST /sanctions`, `DELETE /sanctions/{id}` | федерация | Дисквалификации и отстранения |
| `GET/POST /teams`, `GET/DELETE /teams/{id}`, `GET /teams/{id}/list.docx`, `GET /teams/{id}/order.docx` | федерация | Сборная, список и проект приказа |
| `GET /registry/athletes` | федерация | Реестр с фильтрами |
| `GET /reports/headcount`, `GET /reports/headcount.xlsx` | федерация | Численность и динамика |
| `GET /competitions/{id}/protocol.docx` | публично после публикации | Протокол .docx по образцу Приложения № 5 к Правилам вида спорта |
| `GET /protocol-forms/tasks.docx`, `GET /protocol-forms/product.docx` | публично | Пустые бланки образцов протоколов |
| `GET /athletes/{id}/report.docx`, `GET /me/report.docx` | спортсмен / тренер / федерация | Отчёт о выступлениях |
| `GET /audit` | федерация | Журнал действий с фильтрами |
| `POST /me/certificates`, `GET /me/certificates`, `GET /certificates/{id}.docx` | спортсмен | Справка об участии с QR-кодом |
| `GET /verify/{code}` | публично | Проверка подлинности справки |
| `GET /competitions/{id}/judges.docx`, `GET /judges/{id}/report.docx`, `GET /me/judge/report.docx` | федерация / судья | Документы о судействе |
| `GET /development`, `POST /development/documents`, `GET/DELETE /development/documents/{id}` | федерация, министерство (чтение) | Показатели развития и подтверждающие документы |
| `GET /analytics/effectiveness`, `GET /analytics/effectiveness.xlsx` | федерация, министерство | Эффективность тренеров и организаций |
| `GET/POST /admin/ministry-access` | федерация | Доступ министерства |
| `GET /me/notifications`, `GET /me/notifications/unread-count`, `POST /me/notifications/read`, `GET/PUT /me/settings` | вход | Уведомления и настройка email |

## Структура репозитория

```text
backend/
  app/            модели, схемы и маршруты FastAPI; demo.py — демо-данные, audit.py — журнал действий
  migrations/     миграции Alembic
  tests/          тесты API (SQLite) и интеграционные (PostgreSQL)
frontend/         Dockerfile и nginx.conf — сборка сайта для Docker
frontend/src/
  app/            шапка, сессия и справочники
  pages/          календарь, карточка соревнования, вход, кабинет, админка
  shared/         API-клиент, типы, подписи, общие компоненты
docs/             документация
```
