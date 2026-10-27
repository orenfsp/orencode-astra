# Авторизация MVP

## Поток

`POST /api/v1/auth/register` принимает email, пароль и роль. Email нормализуется, пароль превращается в Argon2id hash. Обычные роли (`athlete`, `coach`, `judge`) доступны без дополнительного подтверждения. Для роли `federation_admin` нужен код из переменной `ADMIN_REGISTRATION_CODE`: он проверяется только во время регистрации и не хранится в PostgreSQL.

`POST /api/v1/auth/login` выдаёт два cookie: `fsp_session` (opaque случайный токен, HttpOnly) и `fsp_csrf` (double-submit токен, доступный frontend). В PostgreSQL хранятся только SHA-256 hashes обоих токенов. Cookie имеют `SameSite=Lax`, `Path=/`; `Secure` включается через `AUTH_COOKIE_SECURE=true`.

Для изменяющих запросов frontend отправляет `X-CSRF-Token` со значением cookie `fsp_csrf`. Backend сравнивает header, cookie и сохранённый hash. Это обязательно для `POST /logout` и `POST /role`.

`GET /me` возвращает пользователя, назначенные роли и активную роль. `POST /role` разрешает выбрать только реально назначенную роль. Backend dependency `require_roles(...)` предназначена для проверки прав в предметных endpoints.

## Admin для dev/demo

Роль `federation_admin` создаётся миграцией. Публичная регистрация её не выдаёт.

После запуска `docker compose up -d --build` создайте или повысьте администратора явной командой (пароль должен содержать 12–128 символов):

```powershell
docker compose exec -e ADMIN_EMAIL="admin@example.test" -e ADMIN_PASSWORD="replace-with-a-long-local-password" backend python -m app.create_admin
```

Команда идемпотентна: для нового email она создаёт пользователя, для существующего назначает `federation_admin`, а при повторном запуске обновляет пароль. Старые сессии этого пользователя отзываются, поэтому после команды нужно войти заново. При входе назначенная `federation_admin` становится активной ролью. Переключиться между назначенными ролями можно через `POST /api/v1/auth/role` с CSRF-заголовком.

Для запуска backend без Docker выполните команду именно из каталога `backend`:

```powershell
Set-Location backend
$env:ADMIN_EMAIL = "admin@example.test"
$env:ADMIN_PASSWORD = "replace-with-a-long-local-password"
python -m app.create_admin
```

Для всех изменяющих competition-запросов браузер должен отправлять cookie сессии и заголовок `X-CSRF-Token`, равный cookie `fsp_csrf`. Отсутствующий/неверный CSRF даёт 403 с сообщением о CSRF; пользователь без активной `federation_admin` получает 403 «Недостаточно прав».

## Границы MVP

- Limiter входа хранится в памяти одного процесса: 5 попыток на комбинацию IP+email за 60 секунд. Для нескольких backend workers нужен Redis или gateway limiter.
- Срок сессии — 12 часов. Просроченные записи удаляются при проверке сессии; для большой нагрузки нужен периодический cleanup job.
- Нет OAuth, Telegram Login, восстановления пароля, email verification и 2FA — это следующие этапы.
- HTTPS завершается reverse proxy; в production обязательно `AUTH_COOKIE_SECURE=true`.

