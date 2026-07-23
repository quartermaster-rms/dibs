import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api, qs } from "../../api/client";
import type { EquipmentDetail, IssueSummary, Severity } from "../../api/types";
import { fmtDateTime } from "../../lib/time";
import { useAsync } from "../../lib/useAsync";
import {
  Badge,
  Button,
  Card,
  CheckboxField,
  Empty,
  ErrorNote,
  Field,
  Input,
  Modal,
  Select,
  Spinner,
  Textarea,
} from "../ui";

function FileIssue({ eq, onDone }: { eq: EquipmentDetail; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [severity, setSeverity] = useState<Severity>("warning");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/equipment/${eq.id}/issues`, { title, severity, description });
      onDone();
    } catch (e2) {
      setErr(e2 as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <Field label="Title">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus />
      </Field>
      <Field label="Severity" hint="Fatal (red) removes it from service; warning is yellow.">
        <Select value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
          <option value="warning">Warning (yellow)</option>
          <option value="fatal">Fatal (red)</option>
        </Select>
      </Field>
      <Field label="Description">
        <Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
      </Field>
      <ErrorNote error={err} />
      <Button type="submit" variant="primary" disabled={busy || !title}>
        File issue
      </Button>
    </form>
  );
}

export function IssuesSection({ eq, onChange }: { eq: EquipmentDetail; onChange: () => void }) {
  const [includeClosed, setIncludeClosed] = useState(false);
  const [q, setQ] = useState("");
  const [filing, setFiling] = useState(false);
  const { data, loading, error, reload } = useAsync(
    () => api.get<IssueSummary[]>(`/equipment/${eq.id}/issues` + qs({ include_closed: includeClosed, q })),
    [eq.id, includeClosed, q],
  );

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-text">Issues</h3>
        <Button variant="primary" onClick={() => setFiling(true)}>
          File a new issue
        </Button>
      </div>
      <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <Input
          placeholder="Search issues…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
        />
        <CheckboxField
          label="Include closed"
          checked={includeClosed}
          onChange={(e) => setIncludeClosed(e.target.checked)}
        />
      </div>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No issues.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((i) => (
            <li
              key={i.id}
              className="-mx-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-1.5 text-sm transition-colors hover:bg-surface-muted"
            >
              <Link
                to={`/issues/${i.id}`}
                className="flex items-center gap-2 font-medium text-text transition-colors hover:text-brand"
              >
                <Badge tone={i.severity === "fatal" ? "danger" : "warning"}>{i.severity}</Badge>
                <span>{i.title}</span>
                {i.status === "closed" && <Badge>closed</Badge>}
              </Link>
              <span className="text-xs text-text-muted">
                {i.reporter_name || i.reporter_id} · {fmtDateTime(i.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {filing && (
        <Modal title="File a new issue" onClose={() => setFiling(false)}>
          <FileIssue
            eq={eq}
            onDone={() => {
              setFiling(false);
              reload();
              onChange();
            }}
          />
        </Modal>
      )}
    </Card>
  );
}
