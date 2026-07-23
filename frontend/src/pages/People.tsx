import { api } from "../api/client";
import type { Person } from "../api/types";
import { Badge, Card, Empty, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { useAsync } from "../lib/useAsync";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function PeoplePage() {
  const { data, loading, error } = useAsync(() => api.get<Person[]>("/people"), []);
  return (
    <div className="space-y-4">
      <PageHeading
        title="People"
        subtitle={data ? `${data.length} ${data.length === 1 ? "person" : "people"}` : undefined}
      />
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No one has used dibs yet.</Empty>
      ) : (
        <Card className="overflow-hidden p-0">
          <ul className="divide-y divide-border">
            {data.map((p) => (
              <li
                key={p.subject}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm transition-colors hover:bg-surface-muted"
              >
                <span className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-semibold text-brand">
                    {initials(p.display_name || p.subject)}
                  </span>
                  <span className="flex flex-col">
                    <span className="font-medium text-text">{p.display_name || p.subject}</span>
                    {p.email && <span className="text-xs text-text-muted">{p.email}</span>}
                  </span>
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
