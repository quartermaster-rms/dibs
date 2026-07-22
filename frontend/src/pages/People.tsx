import { api } from "../api/client";
import type { Person } from "../api/types";
import { Badge, Card, Empty, ErrorNote, Spinner } from "../components/ui";
import { useAsync } from "../lib/useAsync";

export function PeoplePage() {
  const { data, loading, error } = useAsync(() => api.get<Person[]>("/people"), []);
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">People</h1>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No one has used dibs yet.</Empty>
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {data.map((p) => (
              <li key={p.subject} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span>
                  <span className="font-medium">{p.display_name || p.subject}</span>
                  <span className="ml-2 text-xs text-text-muted">{p.email}</span>
                </span>
                <span className="flex flex-wrap items-center gap-1">
                  {p.is_admin ? (
                    <Badge tone="brand">admin</Badge>
                  ) : p.grants.length ? (
                    p.grants.map((g, i) => (
                      <Badge key={i} tone="muted">
                        {g.tier} · {g.scope_name || g.scope_kind}
                      </Badge>
                    ))
                  ) : (
                    <Badge tone="muted">user</Badge>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
