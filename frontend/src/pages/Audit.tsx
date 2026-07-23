import { Fragment, useCallback, useEffect, useState } from "react";

import { ApiError, api, qs } from "../api/client";
import type { AuditEntry } from "../api/types";
import { Button, Card, Empty, ErrorNote, PageHeading, SearchInput, Spinner } from "../components/ui";
import { fmtDateTime } from "../lib/time";

interface Page {
  items: AuditEntry[];
  next_cursor: string | null;
}

function json(v: unknown): string {
  if (v == null) return "—";
  return JSON.stringify(v, null, 2);
}

export function AuditPage() {
  const [action, setAction] = useState("");
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const fetchPage = useCallback(
    async (cursor: string | null) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.get<Page>("/audit" + qs({ action, cursor, limit: 50 }));
        setItems((prev) => (cursor ? [...prev, ...res.items] : res.items));
        setNext(res.next_cursor);
      } catch (e) {
        setError(e as ApiError);
      } finally {
        setLoading(false);
      }
    },
    [action],
  );

  useEffect(() => {
    fetchPage(null);
  }, [fetchPage]);

  return (
    <div className="space-y-4">
      <PageHeading title="Audit log" subtitle="Every recorded state change. Click a row for details." />
      <SearchInput
        placeholder="Filter by action (e.g. session.enable)"
        value={action}
        onChange={(e) => setAction(e.target.value)}
        onClear={() => setAction("")}
        className="max-w-sm"
        aria-label="Filter by action"
      />
      <ErrorNote error={error} />
      <Card className="overflow-hidden p-0">
        {loading && !items.length ? (
          <Spinner />
        ) : !items.length ? (
          <div className="p-4">
            <Empty>No audit entries.</Empty>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm" aria-busy={loading}>
              <thead className="text-xs font-medium uppercase tracking-wide text-text-muted">
                <tr>
                  <th className="w-8 px-4 py-2.5" />
                  <th className="px-4 py-2.5">Time</th>
                  <th className="px-4 py-2.5">Actor</th>
                  <th className="px-4 py-2.5">Action</th>
                  <th className="px-4 py-2.5">Object</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => {
                  const isOpen = openId === a.id;
                  return (
                    <Fragment key={a.id}>
                      <tr
                        onClick={() => setOpenId(isOpen ? null : a.id)}
                        className="cursor-pointer border-t border-border transition-colors hover:bg-surface-muted"
                      >
                        <td className="px-4 py-2.5 text-text-muted">{isOpen ? "▾" : "▸"}</td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-xs text-text-muted">
                          {fmtDateTime(a.ts)}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-text">{a.actor}</td>
                        <td className="px-4 py-2.5 font-mono text-xs text-text">{a.action}</td>
                        <td className="px-4 py-2.5 text-xs text-text-muted">
                          {a.object_type}
                          {a.object_id ? `/${a.object_id.slice(0, 8)}` : ""}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr className="border-t border-border bg-surface-muted/40">
                          <td colSpan={5} className="px-4 py-3">
                            <div className="grid gap-3 sm:grid-cols-2">
                              {(["before", "after"] as const).map((k) => (
                                <div key={k}>
                                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
                                    {k}
                                  </div>
                                  <pre className="overflow-x-auto rounded-control border border-border bg-surface p-3 font-mono text-xs text-text">
                                    {json(a[k])}
                                  </pre>
                                </div>
                              ))}
                            </div>
                            {a.request_id && (
                              <div className="mt-2 text-xs text-text-muted">
                                request_id: <span className="font-mono">{a.request_id}</span>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {next && (
          <div className="border-t border-border p-3 text-center">
            <Button onClick={() => fetchPage(next)} disabled={loading}>
              {loading ? "Loading…" : "Load more"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
