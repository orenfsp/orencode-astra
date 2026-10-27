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
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [reference, setReference] = useState<Reference | null>(null);

  const reloadReference = useCallback(async () => {
    setReference(await api<Reference>("/reference"));
  }, []);

  useEffect(() => {
    api<User>("/auth/me").then(setUser).catch(() => setUser(null));
    reloadReference().catch(() => setReference(null));
  }, [reloadReference]);

  const value = useMemo<SessionValue>(() => ({
    user,
    setUser,
    reference,
    reloadReference,
    switchRole: async (role) => setUser(await api<User>("/auth/role", json("POST", { role }))),
    addRole: async (role) => setUser(await api<User>("/auth/roles", json("POST", { role }))),
    logout: async () => {
      await api<void>("/auth/logout", { method: "POST" });
      setUser(null);
    },
  }), [user, reference, reloadReference]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
