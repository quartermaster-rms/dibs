export type Tier = "none" | "user" | "superuser";
export type Color = "green" | "yellow" | "red";
export type Severity = "warning" | "fatal";

export interface Me {
  subject: string;
  display_name: string;
  email: string;
  groups: string[];
  is_admin: boolean;
  is_sysadmin: boolean;
  csrf_token: string;
}

export interface Status {
  color: Color;
  open_fatal: number;
  open_warning: number;
}

export interface Loc {
  id: string;
  building: string;
  room: string;
}

export interface EquipmentClass {
  id: string;
  name: string;
  description: string;
  department_groups: string[];
  open_use: boolean;
  requires_enable: boolean;
}

export interface Holder {
  subject: string;
  display_name: string;
  started_at: string;
  session_id: string;
}

export interface NextReservation {
  id: string;
  starts_at: string;
  ends_at: string;
  user_id: string;
}

export interface EquipmentRow {
  id: string;
  name: string;
  class_id: string;
  class_name: string;
  location: Loc;
  photo_path: string | null;
  qr_token: string;
  open_use: boolean;
  requires_enable: boolean;
  open_access: boolean;
  enable_gated: boolean;
  status: Status;
  effective_tier: Tier;
  is_admin: boolean;
  can_operate: boolean;
  current_holder: Holder | null;
  next_reservation: NextReservation | null;
  node_count: number;
}

export interface Abilities {
  can_promote: boolean;
  can_grant_superuser: boolean;
  can_demote: boolean;
}

export interface EquipmentDetail extends EquipmentRow {
  class: EquipmentClass;
  my_abilities: Abilities;
}

export interface Reservation {
  id: string;
  equipment_id: string;
  user_id: string;
  created_by: string;
  display_name?: string | null;
  starts_at: string;
  ends_at: string;
  status: "booked" | "completed" | "cancelled";
}

export interface SessionRow {
  id: string;
  subject: string;
  display_name: string;
  started_at: string;
  ended_at: string | null;
  end_cause: "user" | "admin" | null;
}

export interface IssueSummary {
  id: string;
  equipment_id: string;
  title: string;
  severity: Severity;
  status: "open" | "closed";
  reporter_id: string;
  reporter_name: string | null;
  created_at: string;
  last_update_at: string;
  closed_by: string | null;
  closed_at: string | null;
}

export interface IssueUpdate {
  id: string;
  author_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

export interface IssueDetail extends IssueSummary {
  description: string;
  updates: IssueUpdate[];
  photos: { id: string; path: string; update_id: string | null }[];
}

export interface Grant {
  subject: string;
  display_name: string | null;
  email: string | null;
  scope_kind: "item" | "class";
  scope_id: string;
  tier: Tier;
  can_promote: boolean;
  can_grant_superuser: boolean;
  can_demote: boolean;
  granted_by: string;
}

export interface Person {
  subject: string;
  display_name: string;
  email: string;
  is_admin: boolean;
  standing: string;
  grants: { scope_kind: string; scope_id: string; scope_name: string | null; tier: Tier }[];
}

export interface Node {
  id: string;
  equipment_id: string;
  name: string;
  fail_state: "fail_enabled" | "fail_disabled";
  poll_interval_s: number;
  heartbeat_interval_s: number;
  enabled: boolean;
  offline: boolean;
  last_heartbeat_at: string | null;
  last_firmware: string | null;
  key_expiry: string | null;
  has_prev_key: boolean;
  key?: string;
}

export interface Notification {
  id: string;
  body: string;
  read_at: string | null;
  created_at: string;
}

export interface QuotaWindow {
  window: "day" | "week" | "month";
  limit_hours: string | null;
  consumed_hours: string;
  remaining_hours: string | null;
}

export interface Quota {
  reserve: QuotaWindow[];
  usage: QuotaWindow[];
}

export interface QuotaPolicy {
  id: string;
  quota_type: "reserve" | "usage";
  principal: string;
  target_kind: "item" | "class";
  target_id: string;
  window: "day" | "week" | "month";
  limit_hours: string;
  hard_cap: boolean;
  active: boolean;
}

export interface AuditEntry {
  id: string;
  ts: string;
  actor: string;
  action: string;
  object_type: string;
  object_id: string | null;
  before: unknown;
  after: unknown;
  request_id: string | null;
}

export type SettingsMap = Record<string, unknown>;
