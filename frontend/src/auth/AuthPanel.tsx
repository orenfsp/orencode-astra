import { FormEvent, useEffect, useState } from "react";
import "./auth.css";

type User = { id: number; email: string; roles: string[]; active_role: string };
type Mode = "login" | "register";

const AUTH_URL = "http://127.0.0.1:8002/api/v1/auth";
const roleLabels: Record<string, string> = {
  athlete: "Спортсмен",
  coach: "Тренер",
  judge: "Судья",
  federation_admin: "Администратор федерации",
};

function csrfToken() {
  return document.cookie.split("; ").find((value) => value.startsWith("fsp_csrf="))?.split("=").slice(1).join("=") ?? "";
}

async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(`${AUTH_URL}${path}`, { ...init, credentials: "include" });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Ошибка сервера: ${response.status}`);
  }
  return response;
}

export function AuthPanel() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("athlete");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api("/me").then((response) => response.json()).then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body = mode === "register" ? { email, password, role } : { email, password };
      const response = await api(`/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      setUser(await response.json());
      setPassword("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  async function mutate(path: string, body?: object) {
    setLoading(true);
    setError(null);
    try {
      const response = await api(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (path === "/logout") setUser(null);
      else setUser(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  if (loading && !user) return <div className="auth-panel auth-panel--status" role="status">Проверяем сессию…</div>;

  if (user) {
    return (
      <section className="auth-panel" aria-label="Профиль пользователя">
        <div className="auth-user"><span>Вы вошли как</span><strong>{user.email}</strong></div>
        <label>Активная роль
          <select value={user.active_role} disabled={loading} onChange={(event) => mutate("/role", { role: event.target.value })}>
            {user.roles.map((item) => <option value={item} key={item}>{roleLabels[item] ?? item}</option>)}
          </select>
        </label>
        <button type="button" disabled={loading} onClick={() => mutate("/logout")}>{loading ? "Подождите…" : "Выйти"}</button>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  }

  return (
    <section className="auth-panel" aria-label="Авторизация">
      <div className="auth-tabs" role="tablist">
        <button type="button" className={mode === "login" ? "is-active" : ""} onClick={() => { setMode("login"); setError(null); }}>Вход</button>
        <button type="button" className={mode === "register" ? "is-active" : ""} onClick={() => { setMode("register"); setError(null); }}>Регистрация</button>
      </div>
      <form onSubmit={submit}>
        <label>Email<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Пароль<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 12 : 1} maxLength={128} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {mode === "register" && <label>Роль<select value={role} onChange={(event) => setRole(event.target.value)}><option value="athlete">Спортсмен</option><option value="coach">Тренер</option><option value="judge">Судья</option></select></label>}
        <button type="submit" disabled={loading}>{loading ? "Подождите…" : mode === "login" ? "Войти" : "Создать аккаунт"}</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
