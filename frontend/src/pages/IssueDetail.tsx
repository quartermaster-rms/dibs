import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, api } from "../api/client";
import type { IssueDetail as Detail } from "../api/types";
import { useAuth } from "../auth";
import { Badge, Button, Card, ErrorNote, Spinner, Textarea } from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

export function IssueDetail() {
  const { id } = useParams();
  const { me } = useAuth();
  const { data, loading, error, reload } = useAsync(() => api.get<Detail>(`/issues/${id}`), [id]);
  const [body, setBody] = useState("");
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  if (loading) return <Spinner />;
  if (error) return <ErrorNote error={error} />;
  if (!data) return null;

  const addUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/issues/${data.id}/updates`, { body });
      setBody("");
      reload();
    } catch (e2) {
      setErr(e2 as ApiError);
    } finally {
      setBusy(false);
    }
  };

  const close = async () => {
    setErr(null);
    try {
      await api.post(`/issues/${data.id}/close`);
      reload();
    } catch (e) {
      setErr(e as ApiError);
    }
  };

  return (
    <div className="space-y-4">
      <Link
        to={`/equipment/${data.equipment_id}`}
        className="inline-flex items-center gap-1 text-sm text-brand transition-colors hover:text-brand-hover hover:underline"
      >
        ← Equipment
      </Link>
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge tone={data.severity === "fatal" ? "danger" : "warning"}>{data.severity}</Badge>
            <h1 className="text-xl font-bold">{data.title}</h1>
            <Badge tone={data.status === "open" ? "muted" : "success"}>{data.status}</Badge>
          </div>
          {/* close is admin-only, surfaced only to admins (capability-aware) */}
          {me?.is_admin && data.status === "open" && (
            <Button variant="primary" onClick={close}>
              Close issue
            </Button>
          )}
        </div>
        <p className="mt-2 text-sm text-text-muted">
          Filed by {data.reporter_name || data.reporter_id} · {fmtDateTime(data.created_at)}
        </p>
        {data.description && <p className="mt-2 whitespace-pre-wrap text-sm text-text">{data.description}</p>}
        <ErrorNote error={err} />
      </Card>

      <Card>
        <h3 className="mb-3 text-base font-semibold text-text">Update history</h3>
        <ul className="space-y-2">
          {data.updates.map((u) => (
            <li key={u.id} className="border-l-2 border-border pl-3 text-sm">
              <div className="text-xs text-text-muted">
                {u.author_name || u.author_id} · {fmtDateTime(u.created_at)}
              </div>
              <div className="whitespace-pre-wrap">{u.body}</div>
            </li>
          ))}
          {!data.updates.length && <p className="text-sm text-text-muted">No updates yet.</p>}
        </ul>
        <form onSubmit={addUpdate} className="mt-3 space-y-2">
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Post an update…"
            rows={2}
          />
          <Button type="submit" variant="secondary" disabled={busy || !body.trim()}>
            Post update
          </Button>
        </form>
      </Card>
    </div>
  );
}
