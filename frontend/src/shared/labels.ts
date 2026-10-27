import type {
  CalendarPlan, CompetitionFormat, CompetitionLevel, CompetitionStatus, Gender, OrganizationType, Role, TrainingStage,
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
