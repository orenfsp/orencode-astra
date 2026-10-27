import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, errorText, json } from "../shared/api";
import { formatDate } from "../shared/labels";
import type { Notification } from "../shared/types";
import { FormError, GuestNotice, PageTitle, State } from "../shared/ui";

export function NotificationsPage() {
  const { user, refreshUnread } = useSession();
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => { api<Notification[]>("/me/notifications").then(setItems).catch((reason) => setError(errorText(reason))); }, []);
  useEffect(() => { if (user) load(); }, [user, load]);

  async function markAll() {
    setError(null);
    try { await api("/me/notifications/read", json("POST", {})); load(); refreshUnread(); } catch (reason) { setError(errorText(reason)); }
  }

  async function open(item: Notification) {
    if (!item.read_at) {
      await api("/me/notifications/read", json("POST", { ids: [item.id] })).catch(() => undefined);
      refreshUnread();
    }
  }

  if (user === null) return <section className="section"><GuestNotice text="Уведомления доступны после входа." /></section>;
  const unread = items?.filter((item) => !item.read_at).length ?? 0;

  return (
    <section className="section narrow">
      <PageTitle eyebrow="Личный кабинет" title="Уведомления">
        {unread > 0 && <button type="button" className="link-button" onClick={() => void markAll()}>Отметить все прочитанными ({unread})</button>}
      </PageTitle>
      <FormError error={error} />
      {items?.length === 0 && <State code="00" title="Уведомлений нет" text="Здесь появятся решения по заявкам, протоколы, запросы тренеров и напоминания о сроках." />}
      <ul className="notification-list">
        {items?.map((item) => (
          <li key={item.id} className={item.read_at ? "" : "is-unread"}>
            <div>
              <strong>{item.title}</strong>
              <p>{item.body}</p>
              <small className="muted">{formatDate(item.created_at)}</small>
            </div>
            {item.link ? <Link className="link-button" to={item.link} onClick={() => void open(item)}>Открыть</Link>
              : !item.read_at && <button type="button" className="link-button" onClick={() => void open(item).then(load)}>Прочитано</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
