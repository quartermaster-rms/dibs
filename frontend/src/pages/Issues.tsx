import { useState } from "react";
import { Link } from "react-router-dom";

import { api, qs } from "../api/client";
import type { IssueSummary } from "../api/types";
import { Badge, Card, Empty, ErrorNote, PageHeading, Select, Spinner } from "../components/ui";
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
      <PageHeading
        title="Issues"
        subtitle={data ? `${data.length} ${data.length === 1 ? "issue" : "issues"}` : undefined}
      />
      <div className="flex flex-wrap gap-2">
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-[10rem]">
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </Select>
        <Select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="max-w-[10rem]"
        >
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
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs font-medium uppercase tracking-wide text-text-muted">
                <tr>
                  <th className="px-4 py-2.5">Severity</th>
                  <th className="px-4 py-2.5">Title</th>
                  <th className="px-4 py-2.5">Filed</th>
                  <th className="px-4 py-2.5">Updated</th>
                  <th className="px-4 py-2.5">By</th>
                </tr>
              </thead>
              <tbody>
                {data.map((i) => (
                  <tr
                    key={i.id}
                    className="border-t border-border transition-colors hover:bg-surface-muted"
                  >
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-1">
                        <Badge tone={i.severity === "fatal" ? "danger" : "warning"}>
                          {i.severity}
                        </Badge>
                        {i.status === "closed" && <Badge>closed</Badge>}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <Link
                        to={`/issues/${i.id}`}
                        className="font-medium text-text transition-colors hover:text-brand hover:underline"
                      >
                        {i.title}
                      </Link>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-muted">
                      {fmtDateTime(i.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-muted">
                      {fmtDateTime(i.last_update_at)}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-text-muted">
                      {i.reporter_name || i.reporter_id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
