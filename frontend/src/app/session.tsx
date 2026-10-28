import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api, json } from "../shared/api";
import type { Reference, Role, User } from "../shared/types";

type SessionValue = {
  /** undefined — сессия ещё проверяется, null — гость. */
  user: User | null | undefined;
  setUser: (user: User | null) => void;
  switchRole: (role: Role) => Promise<void>;
  addRole: (role: Role) => Promise<void>;
  logout: () => Promise<void>;
  reference: Reference | null;
  reloadReference: () => Promise<void>;
  unread: number;
  refreshUnread: () => void;
};

const SessionContext = createContext<SessionValue | null>(null);
const UNREAD_POLL_MS = 60_000;
// Cookie сессии общая для всех вкладок: о входе, выходе и смене роли сообщаем соседним вкладкам.
const SESSION_EVENT_KEY = "fsp-session-changed";

function announceSessionChange(): void {
  try { window.localStorage.setItem(SESSION_EVENT_KEY, String(Date.now())); } catch { /* хранилище недоступно — вкладки синхронизируются при фокусе */ }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null | undefined>(undefined);
  const [reference, setReference] = useState<Reference | null>(null);
  const [unread, setUnread] = useState(0);

  const reloadReference = useCallback(async () => {
    setReference(await api<Reference>("/reference"));
  }, []);

  const refreshUnread = useCallback(() => {
    api<{ unread: number }>("/me/notifications/unread-count").then((data) => setUnread(data.unread)).catch(() => setUnread(0));
  }, []);

  /** Перечитать, кто сейчас вошёл: в другой вкладке могли войти под другим аккаунтом, выйти или сменить роль. */
  const reloadUser = useCallback(async () => {
    try {
      const next = await api<User>("/auth/me");
      setUserState((current) => (current && current.id === next.id && current.active_role === next.active_role && current.roles.join() === next.roles.join() ? current : next));
    } catch {
      setUserState(null);
    }
  }, []);

  const setUser = useCallback((next: User | null) => {
    setUserState(next);
    announceSessionChange();
  }, []);

  useEffect(() => {
    void reloadUser();
    reloadReference().catch(() => setReference(null));
  }, [reloadUser, reloadReference]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => { if (event.key === SESSION_EVENT_KEY) void reloadUser(); };
    const onVisible = () => { if (document.visibilityState === "visible") void reloadUser(); };
    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", onVisible);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onVisible);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [reloadUser]);

  useEffect(() => {
    if (!user) { setUnread(0); return; }
    refreshUnread();
    const timer = window.setInterval(refreshUnread, UNREAD_POLL_MS);
    return () => window.clearInterval(timer);
  }, [user, refreshUnread]);

  const value = useMemo<SessionValue>(() => ({
    user,
    setUser,
    reference,
    reloadReference,
    unread,
    refreshUnread,
    switchRole: async (role) => {
      try {
        setUser(await api<User>("/auth/role", json("POST", { role })));
      } catch (reason) {
        // Роли нет у текущего аккаунта или сессия закончилась: показываем актуальное состояние, а не устаревшее.
        if (reason instanceof ApiError && (reason.status === 401 || reason.status === 403)) {
          await reloadUser();
          throw new Error("Список ролей обновлён: в другой вкладке выполнен вход под другим аккаунтом или сессия закончилась");
        }
        throw reason;
      }
    },
    addRole: async (role) => setUser(await api<User>("/auth/roles", json("POST", { role }))),
    logout: async () => {
      await api<void>("/auth/logout", { method: "POST" });
      setUser(null);
    },
  }), [user, setUser, reference, reloadReference, unread, refreshUnread, reloadUser]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
