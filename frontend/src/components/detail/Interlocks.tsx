import { useState } from "react";

import { ApiError, api } from "../../api/client";
import type { EquipmentDetail, Node } from "../../api/types";
import { fmtDateTime } from "../../lib/time";
import { useAsync } from "../../lib/useAsync";
import { Badge, Button, Card, Empty, ErrorNote, Field, Input, Modal, Select, Spinner } from "../ui";

function KeyModal({ token, onClose }: { token: string; onClose: () => void }) {
  return (
    <Modal title="Node key (shown once)" onClose={onClose}>
      <p className="mb-2 text-sm text-text-muted">
        Copy this key into the node firmware now. It is stored hashed and cannot be shown again.
      </p>
      <code className="block break-all rounded-control bg-surface-muted p-2 text-sm">{token}</code>
    </Modal>
  );
}

function AddNode({ eq, onAdded }: { eq: EquipmentDetail; onAdded: (key: string) => void }) {
  const [name, setName] = useState("");
  const [failState, setFailState] = useState<"fail_enabled" | "fail_disabled">("fail_enabled");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const node = await api.post<Node>("/nodes", {
        equipment_id: eq.id,
        name,
        fail_state: failState,
      });
      setName("");
      onAdded(node.key!);
    } catch (e2) {
      setErr(e2 as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="door / power" />
      </Field>
      <Field label="Fail state">
        <Select value={failState} onChange={(e) => setFailState(e.target.value as typeof failState)}>
          <option value="fail_enabled">fail_enabled</option>
          <option value="fail_disabled">fail_disabled</option>
        </Select>
      </Field>
      <Button type="submit" variant="primary" disabled={busy}>
        Add interlock
      </Button>
      <div className="w-full">
        <ErrorNote error={err} />
      </div>
    </form>
  );
}

export function InterlocksSection({ eq }: { eq: EquipmentDetail }) {
  const { data, loading, error, reload } = useAsync(() => api.get<Node[]>(`/equipment/${eq.id}/nodes`), [eq.id]);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);

  const patch = async (n: Node, body: Partial<Node>) => {
    setErr(null);
    try {
      await api.patch(`/nodes/${n.id}`, body);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };
  const rotate = async (n: Node) => {
    try {
      const res = await api.post<Node>(`/nodes/${n.id}/rotate-key`);
      setNewKey(res.key!);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };
  const remove = async (n: Node) => {
    try {
      await api.del(`/nodes/${n.id}`);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold">Interlocks (admin)</h3>
      <ErrorNote error={error} />
      <ErrorNote error={err} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No interlock nodes linked.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-medium">{n.name || "node"}</span>
                <Badge>{n.fail_state}</Badge>
                {n.offline && <Badge tone="danger">offline</Badge>}
                {!n.enabled && <Badge tone="warning">killed</Badge>}
                <span className="text-xs text-text-muted">hb {fmtDateTime(n.last_heartbeat_at)}</span>
              </span>
              <span className="flex items-center gap-1">
                <Button variant="ghost" onClick={() => patch(n, { enabled: !n.enabled })}>
                  {n.enabled ? "Kill" : "Un-kill"}
                </Button>
                <Button variant="ghost" onClick={() => rotate(n)}>
                  Rotate key
                </Button>
                <Button variant="ghost" onClick={() => remove(n)}>
                  Remove
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <AddNode eq={eq} onAdded={(k) => { setNewKey(k); reload(); }} />
      {newKey && <KeyModal token={newKey} onClose={() => setNewKey(null)} />}
    </Card>
  );
}
