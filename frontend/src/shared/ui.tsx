import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { statusLabels } from "./labels";
import type { CompetitionStatus } from "./types";

export function State({ code, title, text, action }: { code: string; title: string; text: string; action?: ReactNode }) {
  return (
    <div className="state" role={code === "ERR" ? "alert" : "status"}>
      <span className="state-code">{code}</span>
      <div><strong>{title}</strong><span>{text}</span>{action}</div>
    </div>
  );
}

export function StatusBadge({ status }: { status: CompetitionStatus }) {
  return <span className={`status status--${status}`}><i />{statusLabels[status]}</span>;
}

export function PageTitle({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="page-title">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      {children}
    </div>
  );
}

export function GuestNotice({ text }: { text: string }) {
  return <State code="AUTH" title="Нужен вход" text={text} action={<Link className="button" to="/login">Войти или зарегистрироваться</Link>} />;
}

export function FormError({ error }: { error: string | null }) {
  return error ? <p className="form-error" role="alert">{error}</p> : null;
}

export function Notice({ text }: { text: string | null }) {
  return text ? <p className="form-ok" role="status">{text}</p> : null;
}
