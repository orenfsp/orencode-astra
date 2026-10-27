import { FormEvent, useState } from "react";
import "./auth.css";

export type User = { id: number; email: string; roles: string[]; active_role: string };
type Mode = "login" | "register";

const AUTH_URL = "http://127.0.0.1:8002/api/v1/auth";
export const roleLabels: Record<string, string> = {
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

export async function loadCurrentUser(): Promise<User | null> {
  try {
    const response = await api("/me");
    return await response.json() as User;
  } catch {
    return null;
  }
}

export async function changeActiveRole(role: string): Promise<User> {
  const response = await api("/role", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken() },
    body: JSON.stringify({ role }),
  });
  return await response.json() as User;
}

export async function logoutUser(): Promise<void> {
  await api("/logout", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken() },
  });
}

export function AuthPanel({ user, onSessionChange }: { user: User | null | undefined; onSessionChange: (user: User | null) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("athlete");
  const [adminRegistrationCode, setAdminRegistrationCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body = mode === "register" ? { email, password, role, admin_registration_code: role === "federation_admin" ? adminRegistrationCode : undefined } : { email, password };
      const response = await api(`/${mode}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      onSessionChange(await response.json() as User);
      setPassword("");
      setAdminRegistrationCode("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  async function mutate(path: string, body?: { role?: string }) {
    setLoading(true);
    setError(null);
    try {
      if (path === "/logout") {
        await logoutUser();
        onSessionChange(null);
      } else {
        onSessionChange(await changeActiveRole(String(body?.role ?? "")));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось выполнить запрос");
    } finally {
      setLoading(false);
    }
  }

  if (user === undefined) return <div className="auth-panel auth-panel--status" role="status">Проверяем сессию…</div>;

  if (user) {
    return (
      <section className="auth-panel auth-panel--user" aria-label="Профиль пользователя">
        <div className="auth-user"><span className="auth-session"><i /> Сессия активна</span><strong>{user.email}</strong></div>
        <label className="auth-role">Активная роль
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
        {mode === "register" && <><label>Роль<select value={role} onChange={(event) => setRole(event.target.value)}><option value="athlete">Спортсмен</option><option value="coach">Тренер</option><option value="judge">Судья</option><option value="federation_admin">Администратор федерации</option></select></label>{role === "federation_admin" && <label>Код администратора<input type="password" autoComplete="off" required value={adminRegistrationCode} onChange={(event) => setAdminRegistrationCode(event.target.value)} /></label>}</>}
        <button type="submit" disabled={loading}>{loading ? "Подождите…" : mode === "login" ? "Войти" : "Создать аккаунт"}</button>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
