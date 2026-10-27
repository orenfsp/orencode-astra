import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api, errorText, json } from "../shared/api";
import type { Role, User } from "../shared/types";
import { FormError, PageTitle } from "../shared/ui";

type Mode = "login" | "register";

export function LoginPage() {
  const { user, setUser } = useSession();
  const [mode, setMode] = useState<Mode>("login");
  const [form, setForm] = useState({ email: "", password: "", last_name: "", first_name: "", middle_name: "", role: "athlete" as Role, admin_registration_code: "", pd_consent: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/cabinet" replace />;

  const set = (name: keyof typeof form) => (event: { target: HTMLInputElement | HTMLSelectElement }) =>
    setForm({ ...form, [name]: event.target instanceof HTMLInputElement && event.target.type === "checkbox" ? event.target.checked : event.target.value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body = mode === "login"
        ? { email: form.email, password: form.password }
        : { ...form, middle_name: form.middle_name || null, admin_registration_code: form.role === "federation_admin" ? form.admin_registration_code : undefined };
      setUser(await api<User>(`/auth/${mode}`, json("POST", body)));
    } catch (reason) {
      setError(errorText(reason, "Не удалось выполнить запрос"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="section narrow">
      <PageTitle eyebrow="Единый аккаунт федерации" title={mode === "login" ? "Вход" : "Регистрация"}>
        <p className="lead">Один аккаунт — несколько ролей: спортсмен, тренер, судья. Кабинеты переключаются без повторного входа.</p>
      </PageTitle>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "is-active" : ""} onClick={() => { setMode("login"); setError(null); }}>Вход</button>
        <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "is-active" : ""} onClick={() => { setMode("register"); setError(null); }}>Регистрация</button>
      </div>
      <form className="card form-grid" onSubmit={submit}>
        {mode === "register" && (
          <>
            <label>Фамилия<input required maxLength={120} autoComplete="family-name" value={form.last_name} onChange={set("last_name")} /></label>
            <label>Имя<input required maxLength={120} autoComplete="given-name" value={form.first_name} onChange={set("first_name")} /></label>
            <label>Отчество <small>(если есть)</small><input maxLength={120} autoComplete="additional-name" value={form.middle_name} onChange={set("middle_name")} /></label>
            <label>Первая роль
              <select value={form.role} onChange={set("role")}>
                <option value="athlete">Спортсмен</option>
                <option value="coach">Тренер</option>
                <option value="judge">Судья</option>
                <option value="federation_admin">Сотрудник федерации</option>
              </select>
              <small>Остальные роли можно добавить в кабинете.</small>
            </label>
            {form.role === "federation_admin" && <label className="form-wide">Код администратора<input type="password" required autoComplete="off" value={form.admin_registration_code} onChange={set("admin_registration_code")} /></label>}
          </>
        )}
        <label>Email<input type="email" required autoComplete="email" value={form.email} onChange={set("email")} /></label>
        <label>Пароль<input type="password" required minLength={mode === "register" ? 12 : 1} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password} onChange={set("password")} />
          {mode === "register" && <small>Не короче 12 символов.</small>}
        </label>
        {mode === "register" && (
          <label className="checkbox form-wide">
            <input type="checkbox" required checked={form.pd_consent} onChange={set("pd_consent")} />
            <span>Даю согласие на обработку персональных данных в соответствии с 152-ФЗ. Для несовершеннолетнего спортсмена согласие законного представителя оформляется в профиле.</span>
          </label>
        )}
        <FormError error={error} />
        <button className="button form-wide" disabled={loading}>{loading ? "Подождите…" : mode === "login" ? "Войти" : "Создать аккаунт"}</button>
      </form>
    </section>
  );
}
