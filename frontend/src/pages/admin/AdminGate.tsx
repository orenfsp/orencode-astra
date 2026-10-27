import { useState } from "react";
import type { ReactNode } from "react";
import { useSession } from "../../app/session";
import { errorText } from "../../shared/api";
import { roleLabels } from "../../shared/labels";
import { FormError, GuestNotice, State } from "../../shared/ui";

/** Показывает содержимое только при активной роли федерации; иначе — понятная подсказка. */
export function AdminGate({ children }: { children: ReactNode }) {
  const { user, switchRole } = useSession();
  const [error, setError] = useState<string | null>(null);

  if (user === undefined) return <State code="…" title="Проверяем доступ" text="Сверяем сессию и роль." />;
  if (user === null) return <GuestNotice text="Раздел доступен сотрудникам федерации." />;
  if (user.active_role === "federation_admin") return <>{children}</>;

  const canSwitch = user.roles.includes("federation_admin");
  return (
    <>
      <State code="ROLE" title={canSwitch ? "Переключите кабинет" : "Нет доступа"}
        text={`Сейчас активен кабинет «${roleLabels[user.active_role]}». ${canSwitch ? "Роль федерации уже есть в аккаунте." : "Раздел доступен только сотрудникам федерации."}`}
        action={canSwitch ? <button type="button" className="button" onClick={() => switchRole("federation_admin").catch((reason) => setError(errorText(reason)))}>Открыть кабинет федерации</button> : undefined} />
      <FormError error={error} />
    </>
  );
}
