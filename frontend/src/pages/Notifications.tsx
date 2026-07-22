import { api } from "../api/client";
import type { Notification } from "../api/types";
import { Button, Card, Empty, ErrorNote, Spinner } from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

export function NotificationsPage() {
  const { data, loading, error, reload } = useAsync(
    () => api.get<Notification[]>("/me/notifications"),
    [],
  );

  const markRead = async (id: string) => {
    await api.post(`/me/notifications/${id}/read`);
    reload();
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Inbox</h1>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No notifications.</Empty>
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {data.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className={n.read_at ? "text-text-muted" : "font-medium text-text"}>
                  {n.body}
                  <span className="ml-2 text-xs text-text-muted">{fmtDateTime(n.created_at)}</span>
                </span>
                {!n.read_at && (
                  <Button variant="ghost" onClick={() => markRead(n.id)}>
                    Mark read
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
