import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { errorText } from "../shared/api";
import { roleLabels } from "../shared/labels";
import type { Role } from "../shared/types";
import { useSession } from "./session";

function Logo() {
  return (
    <Link className="brand" to="/" aria-label="ФСП Оренбургской области — на главную">
      <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
        <line x1="10" y1="12" x2="22" y2="20" /><line x1="22" y1="20" x2="32" y2="10" /><line x1="22" y1="20" x2="16" y2="31" /><line x1="22" y1="20" x2="33" y2="28" />
        <circle cx="10" cy="12" r="4.5" className="dot-red" /><circle cx="22" cy="20" r="5" className="dot-blue" />
        <circle cx="32" cy="10" r="3.5" className="dot-blue" /><circle cx="16" cy="31" r="3.5" className="dot-red" /><circle cx="33" cy="28" r="3" className="dot-ink" />
      </svg>
      <span className="brand-short">ФСП</span>
      <span className="brand-region">федерация спортивного<br />программирования · Оренбург</span>
    </Link>
  );
}

export function Header() {
  const { user, switchRole, logout, unread } = useSession();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = user?.active_role === "federation_admin";

  async function onRole(role: Role) {
    setError(null);
    try { await switchRole(role); } catch (reason) { setError(errorText(reason)); }
  }

  async function onLogout() {
    try { await logout(); navigate("/"); } catch (reason) { setError(errorText(reason)); }
  }

  return (
    <header className="site-header">
      <div className="header-card">
        <div className="header-top">
          <Logo />
          <div className="header-session">
            {user === undefined && <span className="muted">…</span>}
            {user === null && <Link className="button button--small" to="/login">Войти</Link>}
            {user && (
              <>
                <label className="role-switch">
                  <span className="sr-only">Активный кабинет</span>
                  <select value={user.active_role} onChange={(event) => void onRole(event.target.value as Role)} title="Переключить кабинет без повторного входа">
                    {user.roles.map((role) => <option key={role} value={role}>{roleLabels[role]}</option>)}
                  </select>
                </label>
                <Link className="bell" to="/notifications" aria-label={unread ? `Уведомления: ${unread} непрочитанных` : "Уведомления"}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a6 6 0 0 0-6 6v3.5L4.5 15v1h15v-1L18 12.5V9a6 6 0 0 0-6-6Zm0 18a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 21Z" /></svg>
                  {unread > 0 && <span className="bell-count">{unread > 99 ? "99+" : unread}</span>}
                </Link>
                <button type="button" className="link-button" onClick={() => void onLogout()}>Выйти</button>
              </>
            )}
            <button type="button" className="menu-toggle" aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}>
              <span className="sr-only">Меню</span><i /><i /><i />
            </button>
          </div>
        </div>
        <nav id="main-nav" className={`header-nav${open ? " is-open" : ""}`} aria-label="Основная навигация" onClick={() => setOpen(false)}>
          <NavLink to="/" end>Календарь</NavLink>
          {!isAdmin && <NavLink to="/start">Новичкам</NavLink>}
          {user && <NavLink to="/cabinet">Кабинет</NavLink>}
          {isAdmin && <NavLink to="/admin" end>Дашборд</NavLink>}
          {isAdmin && <NavLink to="/admin/competitions">Соревнования</NavLink>}
          {isAdmin && <NavLink to="/admin/registry">Реестр</NavLink>}
          {isAdmin && <NavLink to="/admin/rating">Рейтинг</NavLink>}
          {isAdmin && <NavLink to="/admin/ranks">Разряды</NavLink>}
          {isAdmin && <NavLink to="/admin/analytics">Аналитика</NavLink>}
          {user?.active_role === "ministry" && <NavLink to="/ministry">Министерство</NavLink>}
          {isAdmin && <NavLink to="/admin/judges">Судьи</NavLink>}
          {isAdmin && <NavLink to="/admin/reference">Справочники</NavLink>}
          {isAdmin && <NavLink to="/admin/audit">Журнал</NavLink>}
        </nav>
        {error && <p className="header-error" role="alert">{error}</p>}
      </div>
    </header>
  );
}
