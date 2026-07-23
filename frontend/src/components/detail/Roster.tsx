import { useState } from "react";

import { ApiError, api, qs } from "../../api/client";
import type { EquipmentDetail, Grant, Tier } from "../../api/types";
import { useAsync } from "../../lib/useAsync";
import { Badge, Button, Card, Empty, ErrorNote, Field, Help, Input, Select, Spinner } from "../ui";

function PromotePanel({ eq, onDone }: { eq: EquipmentDetail; onDone: () => void }) {
  const ab = eq.my_abilities;
  const [subject, setSubject] = useState("");
  const [tier, setTier] = useState<Tier>("user");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.put("/grants", {
        subject: subject.trim(),
        scope_kind: "item",
        scope_id: eq.id,
        tier,
      });
      setSubject("");
      onDone();
    } catch (e2) {
      setErr(e2 as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
      <Field label="Grant access to">
        <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="username" />
      </Field>
      <Field label="Tier">
        <Select value={tier} onChange={(e) => setTier(e.target.value as Tier)}>
          <option value="user">user</option>
          {ab.can_grant_superuser && <option value="superuser">superuser</option>}
        </Select>
      </Field>
      <Button type="submit" variant="primary" disabled={busy || !subject.trim()}>
        Apply
      </Button>
      <div className="w-full">
        <ErrorNote error={err} />
      </div>
    </form>
  );
}

export function RosterSection({ eq }: { eq: EquipmentDetail }) {
  const ab = eq.my_abilities;
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useAsync(
    () => api.get<Grant[]>(`/equipment/${eq.id}/grants` + qs({ q })),
    [eq.id, q],
  );
  const [err, setErr] = useState<ApiError | null>(null);

  const demote = async (g: Grant) => {
    setErr(null);
    try {
      await api.put("/grants", {
        subject: g.subject,
        scope_kind: g.scope_kind,
        scope_id: g.scope_id,
        tier: "none",
      });
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  return (
    <Card>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold">Access roster</h3>
        <Help>Everyone at user or superuser tier on this item or its class. Admins have implicit access.</Help>
      </div>
      <Input placeholder="Search people…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-2 max-w-xs" />
      <ErrorNote error={error} />
      <ErrorNote error={err} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No user or superuser grants.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((g) => (
            <li key={g.subject + g.scope_id} className="flex items-center justify-between py-1.5 text-sm">
              <span className="flex items-center gap-2">
                {g.display_name || g.subject}
                <Badge tone="brand">{g.tier}</Badge>
                {g.scope_kind === "class" && <Badge>class</Badge>}
              </span>
              {g.demotable && (
                <Button variant="ghost" onClick={() => demote(g)}>
                  Demote
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {ab.can_promote && <PromotePanel eq={eq} onDone={reload} />}
    </Card>
  );
}
