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
    end_year: number | null;
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

export type HistoryItem = { application_id: number; competition: CompetitionBrief; age_group: AgeGroup; place: number | null; score: string | null; result_status: ResultStatus; participants: number };

export type LinkStatus = "pending" | "active" | "suspended" | "ended" | "declined";
export type RequestKind = "assign" | "confirm";
export type RequestStatus = "pending" | "approved" | "rejected";
export type SportRank = "youth_3" | "youth_2" | "youth_1" | "third" | "second" | "first" | "kms";
export type JudgeCategory = "young" | "third" | "second" | "first" | "all_russian";
export type Validity = "none" | "valid" | "expiring" | "expired";

export type CoachLink = {
  id: number;
  coach_id: number;
  coach_name: string;
  athlete: AthleteBrief;
  discipline: Discipline;
  status: LinkStatus;
  created_at: string;
  updated_at: string;
  history: { status: LinkStatus; changed_by: string | null; note: string | null; created_at: string }[];
};

export type AthleteSearchResult = AthleteBrief & { disciplines: Discipline[] };

export type RankRecord = { id: number; rank: SportRank; assigned_on: string; expires_on: string; order_ref: string; validity: Validity };

export type Basis = { application_id: number; competition: CompetitionBrief; place: number | null; score: string | null; result_status: ResultStatus };

export type RankRequest = {
  id: number;
  athlete: AthleteBrief;
  rank: SportRank;
  kind: RequestKind;
  basis: Basis;
  submitted_by: string;
  submitted_role: string;
  status: RequestStatus;
  moderator_comment: string | null;
  created_at: string;
  current: RankRecord | null;
};

export type MyRank = { current: RankRecord | null; history: RankRecord[]; has_coach: boolean; requests: RankRequest[] };

export type CoachAthleteSummary = {
  athlete: AthleteBrief;
  disciplines: Discipline[];
  rank: { rank: SportRank; assigned_on: string; expires_on: string; order_ref: string } | null;
  results: HistoryItem[];
};

export type RankCandidate = { athlete: AthleteBrief; suggested_rank: SportRank; current: RankRecord | null; basis: Basis; pending_request: boolean };

export type JudgeInfo = { category: JudgeCategory | null; category_assigned_on: string | null; category_expires_on: string | null; order_ref: string | null; validity: Validity };

export type JudgeAssignment = { id: number; competition: CompetitionBrief; judge_id: number; judge_name: string; position: RefItem };

export type JudgeRequest = {
  id: number;
  judge_id: number;
  judge_name: string;
  category: JudgeCategory;
  kind: RequestKind;
  justification: string;
  status: RequestStatus;
  moderator_comment: string | null;
  created_at: string;
  current: JudgeInfo;
};

export type MyJudge = { info: JudgeInfo; assignments: JudgeAssignment[]; requests: JudgeRequest[] };

export type JudgeRow = { judge_id: number; name: string; info: JudgeInfo; assignments: number };

export type Deadline = { kind: string; title: string; date: string; days_left: number; severity: "info" | "warning" | "danger"; link: string | null };

export type Notification = { id: number; kind: string; title: string; body: string; link: string | null; created_at: string; read_at: string | null };

export type Dashboard = {
  athletes: number;
  coaches: number;
  judges: number;
  organizations: number;
  competitions_this_year: number;
  participants_this_year: number;
  ranks_this_year: number;
  attention: { title: string; count: number; link: string }[];
  upcoming: { id: number; title: string; date: string; discipline: string; status: CompetitionStatus; approved: number; pending: number }[];
  deadlines: Deadline[];
};

export type RatingItem = { competition_id: number; title: string; date: string; level: CompetitionLevel; competition_type: string; place: number; points: number; rule: string | null };

export type RatingRow = {
  place: number;
  athlete: AthleteBrief;
  rank: SportRank | null;
  base_points: number;
  podiums: number;
  coefficient: string;
  total: string;
  items: RatingItem[];
};

export type RatingRule = { title: string; level: CompetitionLevel; competition_type_id: number | null; first: number; second: number; third: number };

export type RatingSettings = { stability_coefficient: string; stability_min_podiums: number; points: RatingRule[] };

export type Rating = {
  season: number;
  discipline: Discipline;
  age_group: AgeGroup | null;
  min_rank: SportRank | null;
  settings: RatingSettings;
  rows: RatingRow[];
  excluded: { athlete: AthleteBrief; reason: string }[];
};

export type SanctionKind = "disqualification" | "suspension";

export type Sanction = { id: number; athlete: AthleteBrief; kind: SanctionKind; starts_on: string; ends_on: string | null; reason: string; active: boolean };

export type TeamMember = { athlete: AthleteBrief; position: number; is_reserve: boolean; rating_place: number | null; rating_points: string | null; rank: SportRank | null };

export type Team = { id: number; title: string; discipline: Discipline; season: number; age_group: RefItem | null; created_at: string; members: TeamMember[] };

export type RegistryRow = AthleteBrief & {
  disciplines: Discipline[];
  start_year: number | null;
  end_year: number | null;
  training_stage: TrainingStage | null;
  rank: SportRank | null;
  rank_validity: Validity;
  coaches: string[];
  age: number | null;
};

export type Headcount = { years: number[]; total: number[]; sections: { key: string; title: string; rows: { name: string; counts: number[] }[] }[]; note: string };
