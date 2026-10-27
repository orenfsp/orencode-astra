import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, json } from "../shared/api";
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

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [reference, setReference] = useState<Reference | null>(null);
  const [unread, setUnread] = useState(0);

  const reloadReference = useCallback(async () => {
    setReference(await api<Reference>("/reference"));
  }, []);

  const refreshUnread = useCallback(() => {
    api<{ unread: number }>("/me/notifications/unread-count").then((data) => setUnread(data.unread)).catch(() => setUnread(0));
  }, []);

  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch(() => setUser(null));
    reloadReference().catch(() => setReference(null));
  }, [reloadReference]);

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
    switchRole: async (role) => setUser(await api<User>("/auth/role", json("POST", { role }))),
    addRole: async (role) => setUser(await api<User>("/auth/roles", json("POST", { role }))),
    logout: async () => {
      await api<void>("/auth/logout", { method: "POST" });
      setUser(null);
    },
  }), [user, reference, reloadReference, unread, refreshUnread]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
