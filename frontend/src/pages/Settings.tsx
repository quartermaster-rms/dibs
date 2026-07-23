import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import type { EquipmentClass, Loc, QuotaPolicy, SettingsMap } from "../api/types";
import {
  Badge,
  Button,
  Card,
  CheckboxField,
  Empty,
  ErrorNote,
  Field,
  IconButton,
  Input,
  PageHeading,
  SectionHeading,
  Select,
  Spinner,
} from "../components/ui";
import { useAsync } from "../lib/useAsync";

type Group = "reservations" | "delegation" | "device" | "entity" | "access";

const SETTING_META: Record<string, { label: string; help: string; unit?: string; group: Group }> = {
  reservation_slot_granularity_minutes: {
    label: "Slot granularity",
    unit: "min",
    group: "reservations",
    help: "Reservations must start and end on this minute boundary (e.g. 15).",
  },
  max_reservation_days_advance: {
    label: "Max booking lead time",
    unit: "days",
    group: "reservations",
    help: "How far ahead of time a reservation may be booked.",
  },
  node_offline_missed_heartbeats: {
    label: "Offline threshold",
    unit: "beats",
    group: "device",
    help: "Mark an interlock node offline after this many missed heartbeats.",
  },
  desired_state_ttl_multiplier: {
    label: "Desired-state TTL",
    unit: "× poll",
    group: "device",
    help: "How long a node trusts its cached power state, as a multiple of its poll interval.",
  },
  key_rotation_grace_hours: {
    label: "Key rotation grace",
    unit: "hrs",
    group: "device",
    help: "After a node key is rotated, the previous key keeps working for this long.",
  },
  delegation_default_can_promote: {
    label: "Default: can promote",
    group: "delegation",
    help: "New superuser grants may raise a user from none to user by default.",
  },
  delegation_default_can_grant_superuser: {
    label: "Default: can grant superuser",
    group: "delegation",
    help: "New superuser grants may create other superusers by default.",
  },
  delegation_default_can_demote: {
    label: "Default: can demote",
    group: "delegation",
    help: "New superuser grants may lower a user's tier by default.",
  },
  delegation_allow_peer_demote: {
    label: "Allow peer demote",
    group: "delegation",
    help: "Let a superuser demote another superuser in the same scope.",
  },
  delegation_allow_self_demote: {
    label: "Allow self demote",
    group: "delegation",
    help: "Let a superuser demote their own grant.",
  },
  default_open_use: {
    label: "New items open-access",
    group: "entity",
    help: "New equipment/classes are open-access (any authenticated user may Enable) unless changed.",
  },
  default_requires_enable: {
    label: "New items require Enable",
    group: "entity",
    help: "New equipment/classes are enable-gated (have an Enable step) unless changed.",
  },
  dibs_department_groups: {
    label: "Department gate",
    group: "access",
    help: "Only members of these groups may reach dibs (leave empty to allow every authenticated user).",
  },
};

const NUMBER_KEYS = [
  "reservation_slot_granularity_minutes",
  "max_reservation_days_advance",
  "node_offline_missed_heartbeats",
  "desired_state_ttl_multiplier",
  "key_rotation_grace_hours",
];
const BOOL_KEYS = [
  "delegation_default_can_promote",
  "delegation_default_can_grant_superuser",
  "delegation_default_can_demote",
  "delegation_allow_peer_demote",
  "delegation_allow_self_demote",
  "default_open_use",
  "default_requires_enable",
];
const LIST_KEYS = ["dibs_department_groups"];

const GROUPS: { key: Group; title: string }[] = [
  { key: "reservations", title: "Reservations" },
  { key: "delegation", title: "Superuser delegation defaults" },
  { key: "device", title: "Interlock devices" },
  { key: "entity", title: "New-entity defaults" },
  { key: "access", title: "Access" },
];

function PolicyCard() {
  const { data, loading, error, reload } = useAsync(() => api.get<SettingsMap>("/settings"), []);
  const [draft, setDraft] = useState<SettingsMap>({});
  const [err, setErr] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    if (data) setDraft(data);
  }, [data]);

  if (loading) return <Spinner />;
  const set = (k: string, v: unknown) => {
    setDraft((d) => ({ ...d, [k]: v }));
    setSaved(false);
  };
  const save = async () => {
    setErr(null);
    setSaving(true);
    try {
      await api.put("/settings", draft);
      setSaved(true);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <SectionHeading className="mb-3">Runtime policy</SectionHeading>
      <ErrorNote error={error} />
      <div className="space-y-5">
        {GROUPS.map((g) => {
          const keys = Object.keys(SETTING_META).filter((k) => SETTING_META[k].group === g.key);
          const fields = keys.filter((k) => NUMBER_KEYS.includes(k) || LIST_KEYS.includes(k));
          const bools = keys.filter((k) => BOOL_KEYS.includes(k));
          return (
            <section key={g.key} className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                {g.title}
              </h3>
              {fields.length > 0 && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {fields.map((k) => {
                    const m = SETTING_META[k];
                    return NUMBER_KEYS.includes(k) ? (
                      <Field key={k} label={m.label} help={m.help} hint={m.unit}>
                        <Input
                          type="number"
                          value={Number(draft[k] ?? 0)}
                          onChange={(e) => set(k, Number(e.target.value))}
                        />
                      </Field>
                    ) : (
                      <Field key={k} label={m.label} help={m.help} hint="comma-separated group names">
                        <Input
                          value={(Array.isArray(draft[k]) ? (draft[k] as string[]) : []).join(", ")}
                          onChange={(e) =>
                            set(
                              k,
                              e.target.value
                                .split(",")
                                .map((x) => x.trim())
                                .filter(Boolean),
                            )
                          }
                        />
                      </Field>
                    );
                  })}
                </div>
              )}
              {bools.length > 0 && (
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {bools.map((k) => (
                    <CheckboxField
                      key={k}
                      label={SETTING_META[k].label}
                      help={SETTING_META[k].help}
                      checked={!!draft[k]}
                      onChange={(e) => set(k, e.target.checked)}
                    />
                  ))}
                </div>
              )}
            </section>
          );
        })}
      </div>
      <ErrorNote error={err} />
      <div className="mt-4 flex items-center gap-2">
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save policy"}
        </Button>
        {saved && <Badge tone="success">Saved</Badge>}
      </div>
    </Card>
  );
}

function QuotaCard() {
  const { data, loading, error, reload } = useAsync(
    () => api.get<QuotaPolicy[]>("/quota-policies"),
    [],
  );
  const [form, setForm] = useState({
    quota_type: "reserve",
    principal: "everyone",
    target_kind: "item",
    target_id: "",
    window: "week",
    limit_hours: 8,
    hard_cap: false,
  });
  const [err, setErr] = useState<ApiError | null>(null);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await api.post("/quota-policies", form);
      reload();
    } catch (e2) {
      setErr(e2 as ApiError);
    }
  };
  const del = async (id: string) => {
    await api.del(`/quota-policies/${id}`);
    reload();
  };

  return (
    <Card>
      <SectionHeading className="mb-3">Quota policies</SectionHeading>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No quota policies — usage is unlimited.</Empty>
      ) : (
        <ul className="mb-3 divide-y divide-border text-sm">
          {data.map((p) => (
            <li
              key={p.id}
              className="-mx-4 flex items-center justify-between gap-2 px-4 py-2 transition-colors hover:bg-surface-muted"
            >
              <span className="flex flex-wrap items-center gap-1.5">
                <Badge tone="brand">{p.quota_type}</Badge>
                <span className="text-text-muted">
                  {p.principal} · {p.target_kind} · {p.window} · {p.limit_hours}h
                </span>
                {p.hard_cap && <Badge tone="warning">hard cap</Badge>}
                {!p.active && <Badge>inactive</Badge>}
              </span>
              <IconButton
                aria-label="Delete policy"
                className="hover:text-danger"
                onClick={() => del(p.id)}
              >
                ✕
              </IconButton>
            </li>
          ))}
        </ul>
      )}
      <form
        onSubmit={add}
        className="grid grid-cols-2 items-end gap-3 border-t border-border pt-4 sm:grid-cols-3 lg:grid-cols-4"
      >
        <h3 className="col-span-full text-sm font-semibold text-text">Add policy</h3>
        <Field label="Type">
          <Select
            value={form.quota_type}
            onChange={(e) => setForm({ ...form, quota_type: e.target.value })}
          >
            <option value="reserve">reserve</option>
            <option value="usage">usage</option>
          </Select>
        </Field>
        <Field label="Principal">
          <Input
            value={form.principal}
            onChange={(e) => setForm({ ...form, principal: e.target.value })}
          />
        </Field>
        <Field label="Target kind">
          <Select
            value={form.target_kind}
            onChange={(e) => setForm({ ...form, target_kind: e.target.value })}
          >
            <option value="item">item</option>
            <option value="class">class</option>
          </Select>
        </Field>
        <Field label="Target id">
          <Input
            value={form.target_id}
            onChange={(e) => setForm({ ...form, target_id: e.target.value })}
          />
        </Field>
        <Field label="Window">
          <Select value={form.window} onChange={(e) => setForm({ ...form, window: e.target.value })}>
            <option value="day">day</option>
            <option value="week">week</option>
            <option value="month">month</option>
          </Select>
        </Field>
        <Field label="Limit (hours)">
          <Input
            type="number"
            value={form.limit_hours}
            onChange={(e) => setForm({ ...form, limit_hours: Number(e.target.value) })}
          />
        </Field>
        <CheckboxField
          label="Hard cap"
          help="Enforce as an absolute ceiling regardless of other policies."
          checked={form.hard_cap}
          onChange={(e) => setForm({ ...form, hard_cap: e.target.checked })}
          className="self-center"
        />
        <Button type="submit" variant="primary" className="self-end">
          Add policy
        </Button>
        <div className="col-span-full">
          <ErrorNote error={err} />
        </div>
      </form>
    </Card>
  );
}

function EntityCard() {
  const locs = useAsync(() => api.get<Loc[]>("/locations"), []);
  const classes = useAsync(() => api.get<EquipmentClass[]>("/classes"), []);
  const [loc, setLoc] = useState({ building: "", room: "" });
  const [cls, setCls] = useState({ name: "", description: "" });
  const [eq, setEq] = useState({ name: "", class_id: "", location_id: "" });
  const [err, setErr] = useState<ApiError | null>(null);

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try {
      await fn();
      locs.reload();
      classes.reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  return (
    <Card>
      <SectionHeading className="mb-3">Entities</SectionHeading>
      <ErrorNote error={err} />
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Locations</h3>
          {!locs.data?.length ? (
            <Empty>None yet.</Empty>
          ) : (
            <ul className="mb-2 divide-y divide-border text-xs text-text-muted">
              {locs.data.map((l) => (
                <li key={l.id} className="flex items-center justify-between py-1">
                  <span>
                    {l.building} {l.room}
                  </span>
                  <IconButton
                    aria-label={`Delete ${l.building} ${l.room}`}
                    className="h-6 w-6 hover:text-danger"
                    onClick={() => run(() => api.del(`/locations/${l.id}`))}
                  >
                    ✕
                  </IconButton>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-1.5">
            <Input
              placeholder="Building"
              value={loc.building}
              onChange={(e) => setLoc({ ...loc, building: e.target.value })}
            />
            <Input
              placeholder="Room"
              value={loc.room}
              onChange={(e) => setLoc({ ...loc, room: e.target.value })}
            />
            <Button
              aria-label="Add location"
              onClick={() =>
                run(async () => {
                  await api.post("/locations", loc);
                  setLoc({ building: "", room: "" });
                })
              }
            >
              +
            </Button>
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Classes</h3>
          {!classes.data?.length ? (
            <Empty>None yet.</Empty>
          ) : (
            <ul className="mb-2 divide-y divide-border text-xs text-text-muted">
              {classes.data.map((c) => (
                <li key={c.id} className="flex items-center justify-between py-1">
                  <span>{c.name}</span>
                  <IconButton
                    aria-label={`Delete ${c.name}`}
                    className="h-6 w-6 hover:text-danger"
                    onClick={() => run(() => api.del(`/classes/${c.id}`))}
                  >
                    ✕
                  </IconButton>
                </li>
              ))}
            </ul>
          )}
          <div className="flex gap-1.5">
            <Input
              placeholder="Name"
              value={cls.name}
              onChange={(e) => setCls({ ...cls, name: e.target.value })}
            />
            <Button
              aria-label="Add class"
              onClick={() =>
                run(async () => {
                  await api.post("/classes", cls);
                  setCls({ name: "", description: "" });
                })
              }
            >
              +
            </Button>
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-text">Equipment</h3>
          <p className="mb-2 text-xs text-text-muted">Create it, then open it to manage interlocks.</p>
          <div className="space-y-1.5">
            <Input
              placeholder="Name"
              value={eq.name}
              onChange={(e) => setEq({ ...eq, name: e.target.value })}
            />
            <Select
              value={eq.class_id}
              onChange={(e) => setEq({ ...eq, class_id: e.target.value })}
            >
              <option value="">class…</option>
              {classes.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <Select
              value={eq.location_id}
              onChange={(e) => setEq({ ...eq, location_id: e.target.value })}
            >
              <option value="">location…</option>
              {locs.data?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.building} {l.room}
                </option>
              ))}
            </Select>
            <Button
              variant="primary"
              className="w-full"
              onClick={() =>
                run(async () => {
                  await api.post("/equipment", eq);
                  setEq({ name: "", class_id: "", location_id: "" });
                })
              }
              disabled={!eq.name || !eq.class_id || !eq.location_id}
            >
              Add equipment
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

export function SettingsPage() {
  return (
    <div className="space-y-4">
      <PageHeading title="Settings" subtitle="Runtime policy, quotas, and entities." />
      <PolicyCard />
      <QuotaCard />
      <EntityCard />
    </div>
  );
}
