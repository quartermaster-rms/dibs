import { useState } from "react";
import { Link } from "react-router-dom";

import { api, qs } from "../api/client";
import type { IssueSummary } from "../api/types";
import { Badge, Card, Empty, ErrorNote, Select, Spinner } from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

export function IssuesPage() {
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const { data, loading, error } = useAsync(
    () => api.get<IssueSummary[]>("/issues" + qs({ status, severity })),
    [status, severity],
  );

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Issues</h1>
      <div className="flex gap-2">
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-[10rem]">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </Select>
        <Select value={severity} onChange={(e) => setSeverity(e.target.value)} className="max-w-[10rem]">
          <option value="">All severities</option>
          <option value="warning">Warning</option>
          <option value="fatal">Fatal</option>
        </Select>
      </div>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No issues.</Empty>
      ) : (
        <Card>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-text-muted">
              <tr>
                <th className="py-1">Severity</th>
                <th>Title</th>
                <th>Filed</th>
                <th>Updated</th>
                <th>By</th>
              </tr>
            </thead>
            <tbody>
              {data.map((i) => (
                <tr key={i.id} className="border-t border-border">
                  <td className="py-1.5">
                    <Badge tone={i.severity === "fatal" ? "danger" : "warning"}>{i.severity}</Badge>
                    {i.status === "closed" && <Badge>closed</Badge>}
                  </td>
                  <td>
                    <Link to={`/issues/${i.id}`} className="hover:text-brand">
                      {i.title}
                    </Link>
                  </td>
                  <td className="text-xs text-text-muted">{fmtDateTime(i.created_at)}</td>
                  <td className="text-xs text-text-muted">{fmtDateTime(i.last_update_at)}</td>
                  <td className="text-xs text-text-muted">{i.reporter_name || i.reporter_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
