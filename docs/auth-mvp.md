# Авторизация MVP

## Поток

`POST /api/v1/auth/register` принимает email, пароль и публичную роль (`athlete`, `coach`, `judge`). Email нормализуется, пароль превращается в Argon2id hash. Роль `federation_admin` через публичную регистрацию недоступна.

`POST /api/v1/auth/login` выдаёт два cookie: `fsp_session` (opaque случайный токен, HttpOnly) и `fsp_csrf` (double-submit токен, доступный frontend). В PostgreSQL хранятся только SHA-256 hashes обоих токенов. Cookie имеют `SameSite=Lax`, `Path=/`; `Secure` включается через `AUTH_COOKIE_SECURE=true`.

Для изменяющих запросов frontend отправляет `X-CSRF-Token` со значением cookie `fsp_csrf`. Backend сравнивает header, cookie и сохранённый hash. Это обязательно для `POST /logout` и `POST /role`.

`GET /me` возвращает пользователя, назначенные роли и активную роль. `POST /role` разрешает выбрать только реально назначенную роль. Backend dependency `require_roles(...)` предназначена для проверки прав в предметных endpoints.

## Admin для dev/demo

После миграций администратор создаётся только явной командой без пароля в репозитории:

```powershell
$env:ADMIN_EMAIL = "admin@example.test"
$env:ADMIN_PASSWORD = "use-a-long-local-secret"
python -m app.create_admin
```

## Границы MVP

- Limiter входа хранится в памяти одного процесса: 5 попыток на комбинацию IP+email за 60 секунд. Для нескольких backend workers нужен Redis или gateway limiter.
- Срок сессии — 12 часов. Просроченные записи удаляются при проверке сессии; для большой нагрузки нужен периодический cleanup job.
- Нет OAuth, Telegram Login, восстановления пароля, email verification и 2FA — это следующие этапы.
- HTTPS завершается reverse proxy; в production обязательно `AUTH_COOKIE_SECURE=true`.
