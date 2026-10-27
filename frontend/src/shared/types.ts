export type Role = "athlete" | "coach" | "judge" | "federation_admin";

export type User = { id: number; email: string; roles: Role[]; active_role: Role; full_name: string | null };

export type RefItem = { id: number; name: string };
export type Discipline = RefItem & { code: string };
export type AgeGroup = RefItem & { min_age: number; max_age: number | null };
export type CompetitionType = RefItem & { is_active: boolean };
export type OrganizationType = "school" | "university" | "college" | "sport_school" | "club" | "other";
export type Organization = RefItem & { org_type: OrganizationType; municipality: RefItem | null; is_active: boolean };

export type Reference = {
  disciplines: Discipline[];
  competition_types: CompetitionType[];
  age_groups: AgeGroup[];
  municipalities: RefItem[];
  organizations: Organization[];
  judge_positions: RefItem[];
};

export type CompetitionStatus = "draft" | "registration_open" | "registration_closed" | "upcoming" | "ongoing" | "completed";
export type CompetitionLevel = "regional" | "interregional" | "all_russian";
export type CompetitionFormat = "offline" | "online" | "mixed";
export type CalendarPlan = "none" | "regional" | "ekp";

export type Competition = {
  id: number;
  title: string;
  discipline: Discipline;
  competition_type: RefItem;
  level: CompetitionLevel;
  age_groups: AgeGroup[];
  date: string;
  end_date: string;
  location: string;
  description: string;
  format: CompetitionFormat;
  registration_start: string;
  registration_end: string;
  calendar_plan: CalendarPlan;
  calendar_plan_number: string | null;
  regulation_filename: string | null;
  protocol_published_at: string | null;
  status: CompetitionStatus;
  is_archived: boolean;
};

export type CompetitionPayload = {
  title: string;
  discipline_id: number;
  competition_type_id: number;
  level: CompetitionLevel;
  age_group_ids: number[];
  date: string;
  end_date: string;
  location: string;
  description: string;
  format: CompetitionFormat;
  registration_start: string;
  registration_end: string;
  calendar_plan: CalendarPlan;
  calendar_plan_number: string | null;
  status?: CompetitionStatus;
};

export type Gender = "male" | "female";
export type TrainingStage = "initial" | "training" | "improvement" | "highest";

export type MyProfile = {
  profile: {
    last_name: string;
    first_name: string;
    middle_name: string | null;
    birth_date: string | null;
    gender: Gender | null;
    municipality: RefItem | null;
    phone: string | null;
  } | null;
  athlete: {
    organization: Organization | null;
    disciplines: Discipline[];
    start_year: number | null;
    training_stage: TrainingStage | null;
    guardian_name: string | null;
    guardian_phone: string | null;
    guardian_consent_at: string | null;
    rusada_completed_on: string | null;
    rusada_certificate_url: string | null;
  } | null;
  coach: { organization: Organization | null } | null;
  age: number | null;
  is_minor: boolean;
  pd_consent_at: string | null;
};

export type ApplicationStatus = "pending" | "approved" | "rejected" | "withdrawn";
export type ResultStatus = "ok" | "dns" | "dsq";

export type CompetitionBrief = Pick<Competition, "id" | "title" | "date" | "end_date" | "level" | "discipline" | "competition_type">;

export type AthleteBrief = { id: number; full_name: string; birth_date: string | null; municipality: string | null; organization: string | null };

export type ResultInfo = { score: string | null; result_status: ResultStatus; place: number | null };

export type Application = {
  id: number;
  competition: CompetitionBrief;
  athlete: AthleteBrief;
  age_group: AgeGroup;
  status: ApplicationStatus;
  submitted_role: string;
  moderator_comment: string | null;
  created_at: string;
  decided_at: string | null;
  result: ResultInfo | null;
};

export type Eligibility = {
  eligible: boolean;
  reasons: string[];
  age: number | null;
  age_group: AgeGroup | null;
  application_id: number | null;
  application_status: ApplicationStatus | null;
};

export type ProtocolRow = { application_id: number; place: number | null; athlete: AthleteBrief; score: string | null; result_status: ResultStatus | null };

export type Protocol = {
  competition: CompetitionBrief;
  location: string;
  published_at: string | null;
  is_complete: boolean;
  groups: { age_group: AgeGroup; rows: ProtocolRow[] }[];
};

export type HistoryItem = { competition: CompetitionBrief; age_group: AgeGroup; place: number | null; score: string | null; result_status: ResultStatus; participants: number };
