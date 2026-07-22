import { useCallback, useEffect, useState } from "react";

import { ApiError, api, qs } from "../api/client";
import type { AuditEntry } from "../api/types";
import { Button, Card, Empty, ErrorNote, Input, Spinner } from "../components/ui";
import { fmtDateTime } from "../lib/time";

interface Page {
  items: AuditEntry[];
  next_cursor: string | null;
}

export function AuditPage() {
  const [action, setAction] = useState("");
  const [items, setItems] = useState<AuditEntry[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

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
      <h1 className="text-xl font-bold">Audit log</h1>
      <Input
        placeholder="Filter by action (e.g. session.enable)"
        value={action}
        onChange={(e) => setAction(e.target.value)}
        className="max-w-sm"
      />
      <ErrorNote error={error} />
      <Card>
        {loading && !items.length ? (
          <Spinner />
        ) : !items.length ? (
          <Empty>No audit entries.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-text-muted">
                <tr>
                  <th className="py-1">Time</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Object</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} className="border-t border-border">
                    <td className="py-1.5 text-xs text-text-muted">{fmtDateTime(a.ts)}</td>
                    <td className="text-xs">{a.actor}</td>
                    <td className="font-mono text-xs">{a.action}</td>
                    <td className="text-xs text-text-muted">
                      {a.object_type}
                      {a.object_id ? `/${a.object_id.slice(0, 8)}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {next && (
          <div className="mt-3 text-center">
            <Button onClick={() => fetchPage(next)} disabled={loading}>
              Load more
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
