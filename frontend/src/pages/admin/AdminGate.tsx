import { useState } from "react";
import type { ReactNode } from "react";
import { useSession } from "../../app/session";
import { errorText } from "../../shared/api";
import { roleLabels } from "../../shared/labels";
import type { Role } from "../../shared/types";
import { FormError, GuestNotice, State } from "../../shared/ui";

/** Показывает содержимое только при подходящей активной роли (по умолчанию — федерация); иначе — понятная подсказка. */
export function AdminGate({ children, roles = ["federation_admin"] }: { children: ReactNode; roles?: Role[] }) {
  const { user, switchRole } = useSession();
  const [error, setError] = useState<string | null>(null);

  if (user === undefined) return <State code="…" title="Проверяем доступ" text="Сверяем сессию и роль." />;
  if (user === null) return <GuestNotice text={roles.includes("ministry") ? "Раздел доступен федерации и министерству спорта." : "Раздел доступен сотрудникам федерации."} />;
  if (roles.includes(user.active_role)) return <>{children}</>;

  const target = roles.find((role) => user.roles.includes(role));
  return (
    <>
      <State code="ROLE" title={target ? "Переключите кабинет" : "Нет доступа"}
        text={`Сейчас активен кабинет «${roleLabels[user.active_role]}». ${target ? `Роль «${roleLabels[target]}» уже есть в аккаунте.` : "У аккаунта нет доступа к этому разделу."}`}
        action={target ? <button type="button" className="button" onClick={() => switchRole(target).catch((reason) => setError(errorText(reason)))}>Открыть кабинет «{roleLabels[target]}»</button> : undefined} />
      <FormError error={error} />
    </>
  );
}
