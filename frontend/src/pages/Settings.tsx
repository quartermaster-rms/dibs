import { useEffect, useState } from "react";

import { ApiError, api } from "../api/client";
import type { EquipmentClass, Loc, QuotaPolicy, SettingsMap } from "../api/types";
import { Badge, Button, Card, Empty, ErrorNote, Field, Input, Select, Spinner } from "../components/ui";
import { useAsync } from "../lib/useAsync";

const NUMBER_KEYS = [
  "reservation_slot_granularity_minutes",
  "max_reservation_days_advance",
  "node_offline_missed_heartbeats",
  "desired_state_ttl_multiplier",
  "key_rotation_grace_hours",
  "digest_hour_local",
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

function PolicyCard() {
  const { data, loading, error, reload } = useAsync(() => api.get<SettingsMap>("/settings"), []);
  const [draft, setDraft] = useState<SettingsMap>({});
  const [err, setErr] = useState<ApiError | null>(null);
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
    try {
      await api.put("/settings", draft);
      setSaved(true);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  return (
    <Card>
      <h2 className="mb-3 text-lg font-semibold">Runtime policy</h2>
      <ErrorNote error={error} />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {NUMBER_KEYS.map((k) => (
          <Field key={k} label={k}>
            <Input
              type="number"
              value={Number(draft[k] ?? 0)}
              onChange={(e) => set(k, Number(e.target.value))}
            />
          </Field>
        ))}
        {LIST_KEYS.map((k) => (
          <Field key={k} label={k} hint="comma-separated group names">
            <Input
              value={(Array.isArray(draft[k]) ? (draft[k] as string[]) : []).join(", ")}
              onChange={(e) =>
                set(
                  k,
                  e.target.value.split(",").map((x) => x.trim()).filter(Boolean),
                )
              }
            />
          </Field>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {BOOL_KEYS.map((k) => (
          <label key={k} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={!!draft[k]} onChange={(e) => set(k, e.target.checked)} />
            {k}
          </label>
        ))}
      </div>
      <ErrorNote error={err} />
      <div className="mt-3 flex items-center gap-2">
        <Button variant="primary" onClick={save}>
          Save policy
        </Button>
        {saved && <span className="text-sm text-success">Saved</span>}
      </div>
    </Card>
  );
}

function QuotaCard() {
  const { data, loading, error, reload } = useAsync(() => api.get<QuotaPolicy[]>("/quota-policies"), []);
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
      <h2 className="mb-3 text-lg font-semibold">Quota policies</h2>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No quota policies (unlimited).</Empty>
      ) : (
        <ul className="mb-3 divide-y divide-border text-sm">
          {data.map((p) => (
            <li key={p.id} className="flex items-center justify-between py-1.5">
              <span>
                <Badge tone="brand">{p.quota_type}</Badge> {p.principal} · {p.target_kind} · {p.window} ·{" "}
                {p.limit_hours}h {p.hard_cap && <Badge tone="warning">hard cap</Badge>}
                {!p.active && <Badge>inactive</Badge>}
              </span>
              <Button variant="ghost" onClick={() => del(p.id)}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
        <Field label="Type">
          <Select value={form.quota_type} onChange={(e) => setForm({ ...form, quota_type: e.target.value })}>
            <option value="reserve">reserve</option>
            <option value="usage">usage</option>
          </Select>
        </Field>
        <Field label="Principal">
          <Input value={form.principal} onChange={(e) => setForm({ ...form, principal: e.target.value })} />
        </Field>
        <Field label="Target kind">
          <Select value={form.target_kind} onChange={(e) => setForm({ ...form, target_kind: e.target.value })}>
            <option value="item">item</option>
            <option value="class">class</option>
          </Select>
        </Field>
        <Field label="Target id">
          <Input value={form.target_id} onChange={(e) => setForm({ ...form, target_id: e.target.value })} />
        </Field>
        <Field label="Window">
          <Select value={form.window} onChange={(e) => setForm({ ...form, window: e.target.value })}>
            <option value="day">day</option>
            <option value="week">week</option>
            <option value="month">month</option>
          </Select>
        </Field>
        <Field label="Limit h">
          <Input
            type="number"
            value={form.limit_hours}
            onChange={(e) => setForm({ ...form, limit_hours: Number(e.target.value) })}
          />
        </Field>
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            checked={form.hard_cap}
            onChange={(e) => setForm({ ...form, hard_cap: e.target.checked })}
          />
          hard cap
        </label>
        <Button type="submit" variant="primary">
          Add
        </Button>
        <div className="w-full">
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
      <h2 className="mb-3 text-lg font-semibold">Entities</h2>
      <ErrorNote error={err} />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <h3 className="mb-1 text-sm font-semibold">Locations</h3>
          <ul className="mb-2 text-xs text-text-muted">
            {locs.data?.map((l) => (
              <li key={l.id} className="flex justify-between">
                {l.building} {l.room}
                <button onClick={() => run(() => api.del(`/locations/${l.id}`))} className="text-danger">
                  ×
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-1">
            <Input placeholder="Building" value={loc.building} onChange={(e) => setLoc({ ...loc, building: e.target.value })} />
            <Input placeholder="Room" value={loc.room} onChange={(e) => setLoc({ ...loc, room: e.target.value })} />
            <Button onClick={() => run(async () => { await api.post("/locations", loc); setLoc({ building: "", room: "" }); })}>+</Button>
          </div>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-semibold">Classes</h3>
          <ul className="mb-2 text-xs text-text-muted">
            {classes.data?.map((c) => (
              <li key={c.id} className="flex justify-between">
                {c.name}
                <button onClick={() => run(() => api.del(`/classes/${c.id}`))} className="text-danger">
                  ×
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-1">
            <Input placeholder="Name" value={cls.name} onChange={(e) => setCls({ ...cls, name: e.target.value })} />
            <Button onClick={() => run(async () => { await api.post("/classes", cls); setCls({ name: "", description: "" }); })}>+</Button>
          </div>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-semibold">Equipment</h3>
          <p className="mb-2 text-xs text-text-muted">Create then open it to manage interlocks.</p>
          <div className="space-y-1">
            <Input placeholder="Name" value={eq.name} onChange={(e) => setEq({ ...eq, name: e.target.value })} />
            <Select value={eq.class_id} onChange={(e) => setEq({ ...eq, class_id: e.target.value })}>
              <option value="">class…</option>
              {classes.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
            <Select value={eq.location_id} onChange={(e) => setEq({ ...eq, location_id: e.target.value })}>
              <option value="">location…</option>
              {locs.data?.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.building} {l.room}
                </option>
              ))}
            </Select>
            <Button
              variant="primary"
              onClick={() => run(async () => { await api.post("/equipment", eq); setEq({ name: "", class_id: "", location_id: "" }); })}
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
      <h1 className="text-xl font-bold">Settings</h1>
      <PolicyCard />
      <QuotaCard />
      <EntityCard />
    </div>
  );
}
