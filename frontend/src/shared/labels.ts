import type {
  ApplicationStatus, CalendarPlan, CompetitionFormat, CompetitionLevel, CompetitionStatus, Gender, JudgeCategory, LinkStatus,
  OrganizationType, RequestKind, RequestStatus, ResultStatus, Role, SportRank, TrainingStage, Validity,
} from "./types";

export const roleLabels: Record<Role, string> = {
  athlete: "Спортсмен",
  coach: "Тренер",
  judge: "Судья",
  federation_admin: "Федерация",
};

export const statusLabels: Record<CompetitionStatus, string> = {
  draft: "Черновик",
  upcoming: "Скоро",
  registration_open: "Приём заявок",
  registration_closed: "Приём заявок закрыт",
  ongoing: "Идёт сейчас",
  completed: "Завершено",
};

export const levelLabels: Record<CompetitionLevel, string> = {
  regional: "Региональное",
  interregional: "Межрегиональное",
  all_russian: "Всероссийское",
};

export const formatLabels: Record<CompetitionFormat, string> = {
  offline: "Очно",
  online: "Онлайн",
  mixed: "Смешанный",
};

export const planLabels: Record<CalendarPlan, string> = {
  none: "Не включено",
  regional: "Календарный план Оренбургской области",
  ekp: "ЕКП Минспорта России",
};

export const organizationTypeLabels: Record<OrganizationType, string> = {
  school: "Школа",
  university: "Вуз",
  college: "Колледж",
  sport_school: "Спортивная школа",
  club: "Клуб",
  other: "Другое",
};

export const genderLabels: Record<Gender, string> = { male: "Мужской", female: "Женский" };

export const stageLabels: Record<TrainingStage, string> = {
  initial: "Начальная подготовка",
  training: "Учебно-тренировочный этап",
  improvement: "Совершенствование спортивного мастерства",
  highest: "Высшее спортивное мастерство",
};

export function keys<T extends string>(labels: Record<T, string>): T[] {
  return Object.keys(labels) as T[];
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(parsed);
}

export function formatRange(start: string, end: string): string {
  return start === end ? formatDate(start) : `${formatDate(start)} — ${formatDate(end)}`;
}

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  pending: "На модерации",
  approved: "Одобрена",
  rejected: "Отклонена",
  withdrawn: "Отозвана",
};

export const resultStatusLabels: Record<ResultStatus, string> = {
  ok: "Результат",
  dns: "Не явился",
  dsq: "Дисквалифицирован",
};

export function birthYear(value: string | null): string {
  return value ? value.slice(0, 4) : "—";
}

export const linkStatusLabels: Record<LinkStatus, string> = {
  pending: "Ждёт подтверждения",
  active: "Активна",
  suspended: "Приостановлена",
  ended: "Завершена",
  declined: "Отклонена",
};

export const requestStatusLabels: Record<RequestStatus, string> = { pending: "На рассмотрении", approved: "Одобрена", rejected: "Отклонена" };

export const requestKindLabels: Record<RequestKind, string> = { assign: "Присвоение", confirm: "Подтверждение" };

export const rankLabels: Record<SportRank, string> = {
  youth_3: "3 юношеский",
  youth_2: "2 юношеский",
  youth_1: "1 юношеский",
  third: "3 спортивный",
  second: "2 спортивный",
  first: "1 спортивный",
  kms: "КМС",
};

export const categoryLabels: Record<JudgeCategory, string> = {
  young: "Юный спортивный судья",
  third: "Судья 3 категории",
  second: "Судья 2 категории",
  first: "Судья 1 категории",
  all_russian: "Судья всероссийской категории",
};

export const validityLabels: Record<Validity, string> = { none: "нет", valid: "действует", expiring: "скоро истекает", expired: "истёк" };

/** Срок действия по умолчанию для формы решения федерации (лет); федерация проверяет и меняет. */
export const rankValidityYears: Record<SportRank, number> = { youth_3: 2, youth_2: 2, youth_1: 2, third: 2, second: 2, first: 2, kms: 3 };
export const categoryValidityYears: Record<JudgeCategory, number> = { young: 1, third: 2, second: 2, first: 4, all_russian: 4 };

export function addYears(isoDate: string, years: number): string {
  const [year, rest] = [Number(isoDate.slice(0, 4)), isoDate.slice(4)];
  return `${year + years}${rest}`;
}

export function todayIso(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function daysLeftText(days: number): string {
  if (days < 0) return `просрочено на ${-days} дн.`;
  if (days === 0) return "сегодня";
  return `через ${days} дн.`;
}
