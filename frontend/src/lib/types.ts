export interface Me {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
}

export interface Today {
  gregorian: string;
  jalali_year: number;
  jalali_month: number;
  jalali_day: number;
  month_name: string;
  time: string;
}

export interface Task {
  revision: string;
  id: number;
  title: string;
  jalali_year: number;
  jalali_month: number;
  jalali_day: number;
  jalali_date_str: string;
  month_name: string;
  gregorian_date: string;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number | null;
  status: "running" | "paused" | "done";
  accumulated_minutes: number;
  segment_started_at: string | null;
  tag_id: number | null;
  tag_name: string | null;
  entered_main_system: boolean;
  outside_company: boolean;
  planned_flag: boolean;
  fill_minutes: number;
  adjust_minutes: number;
  report_type: string | null;
  report_type_id: number | null;
  tag_report_type: string | null;
  meeting_with: string | null;
  company_type: string | null;
  company_project: string | null;
  company_story: string | null;
}

export interface Tag {
  id: number;
  name: string;
  budget_minutes: number | null;
  budget_since: string | null;
  spent_minutes: number | null;
  budget_percent: number | null;
  report_type_id: number | null;
  story_id: number | null;
  report_type: string | null;
  project: string | null;
  story: string | null;
  fill_weight: number | null;
  task_count?: number;
  planned_count?: number;
  archived_count?: number;
}

export interface Planned {
  id: number;
  title: string;
  jalali_year: number;
  jalali_month: number;
  jalali_day: number;
  jalali_date_str: string;
  tag_id: number | null;
  tag_name: string | null;
  gregorian: string | null;
  overdue: boolean;
}

export interface PresenceSegment {
  id: number;
  start: string;
  end: string | null;
  minutes: number;
  open: boolean;
  kind: string | null;
  note: string | null;
}

export interface Presence {
  status: "none" | "in" | "break" | "done";
  segments: PresenceSegment[];
  total_minutes: number;
  task_minutes: number;
  fill_minutes: number;
  first_task_start: string | null;
  running_task: string | null;
  running_task_id: number | null;
  paused_task: string | null;
  needs_checkin: boolean;
  since: string | null;
  server_time: string;
}

export interface Catalog {
  types: { id: number | null; name: string }[];
  projects: { id: number; name: string; stories: { id: number; name: string }[] }[];
}

export interface FillItem {
  id: number;
  title: string;
  tag_name: string | null;
  minutes: number;
  weight: number;
  meeting: boolean;
  fill_minutes: number;
  suggested: number;
  cap: number;
}

export interface FillSuggestion {
  date: string;
  percent: number;
  presence_minutes: number;
  usable_presence_minutes: number;
  warnings: string[];
  blocked: boolean;
  task_minutes: number;
  target_minutes: number;
  needed_minutes: number;
  allowed_minutes: number;
  suggested_total: number;
  current_fill_total: number;
  items: FillItem[];
}

export interface Settings {
  daily_goal_minutes: number;
  weekly_goal_minutes: number;
  fill_target_percent: number;
  google_sheet_url: string;
  backup_setup_done: boolean;
  backup_service_email: string;
}

export interface GoalProgress {
  daily_goal_minutes: number;
  weekly_goal_minutes: number;
  today_minutes: number;
  week_minutes: number;
}

export interface Segment {
  started_at: string;
  ended_at: string | null;
  started_label: string;
  ended_label: string | null;
  minutes: number;
  ongoing: boolean;
}

export interface Comparison {
  kind: string;
  label: string;
  days: number | null;
  current_label: string;
  prev_label: string;
  current_minutes: number;
  prev_minutes: number;
  diff_minutes: number;
  diff_percent: number | null;
}

export interface Dashboard {
  total_minutes: number;
  task_count: number;
  running_count: number;
  paused_count: number;
  active_days: number;
  days_in_month: number | null;
  avg_daily_minutes: number;
  best_day: { date: string; minutes: number } | null;
  daily_goal_minutes: number;
  by_day: { date: string; minutes: number }[];
  by_month: { date: string; month_name: string; minutes: number }[];
  by_tag: { tag_id: number | null; tag_name: string; minutes: number; count: number }[];
  comparison: Comparison | null;
}

export interface TagSummary {
  tag: { id: number | null; name: string };
  budget: Tag | null;
  recent: { title: string; date: string; minutes: number }[];
  total_minutes: number;
  task_count: number;
  day_count: number;
  avg_per_day_minutes: number;
  first_date: string | null;
  last_date: string | null;
  open_count: number;
  open_minutes: number;
  by_month: { date: string; month_name: string; minutes: number }[];
  top_titles: { title: string; minutes: number; count: number }[];
}

export interface TimesheetData {
  week_start: string;
  week_end: string;
  days: { gregorian: string; weekday: string; jalali_year: number; jalali_month: number; jalali_day: number; month_name: string; is_today: boolean }[];
  rows: { tag_id: number | null; tag_name: string; minutes: number[]; total: number }[];
  day_totals: number[];
  total: number;
  prev: string;
  next: string;
}

export interface CalendarEvent {
  title: string;
  holiday: boolean;
  kind: string;
  approx?: boolean;
}

export interface CalendarDay {
  day: number;
  gregorian: string;
  weekday: number;
  hijri: { year: number; month: number; day: number; month_name: string; exact: boolean };
  holiday: boolean;
  events: CalendarEvent[];
  minutes: number;
  task_count: number;
  planned_count: number;
}

export interface CalendarMonth {
  jalali_year: number;
  jalali_month: number;
  month_name: string;
  days_in_month: number;
  first_weekday: number;
  days: CalendarDay[];
}

export interface EntryReportRow {
  date: string;
  total_tasks: number;
  entered_tasks: number;
  total_minutes: number;
  all_entered: boolean;
}

export interface AdminUser {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
}
