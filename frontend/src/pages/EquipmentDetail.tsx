import { useParams } from "react-router-dom";

import { api } from "../api/client";
import type { EquipmentDetail as Detail, Quota, SessionRow } from "../api/types";
import { InterlocksSection } from "../components/detail/Interlocks";
import { IssuesSection } from "../components/detail/Issues";
import { ReservationsSection } from "../components/detail/Reservations";
import { RosterSection } from "../components/detail/Roster";
import { EnableControl } from "../components/EnableControl";
import { Badge, Card, Empty, ErrorNote, Spinner, StatusDot } from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

function QuotaSection({ equipmentId }: { equipmentId: string }) {
  const { data } = useAsync(() => api.get<Quota>(`/me/quota?equipment_id=${equipmentId}`), [equipmentId]);
  if (!data) return null;
  const line = (w: Quota["reserve"][number]) =>
    `${w.window}: ${w.remaining_hours ?? "∞"}${w.limit_hours ? ` / ${w.limit_hours}h` : " (unlimited)"}`;
  return (
    <Card>
      <h3 className="mb-1 text-sm font-semibold">My quota remaining</h3>
      <div className="grid grid-cols-1 gap-1 text-xs text-text-muted sm:grid-cols-2">
        <div>Reserve — {data.reserve.map(line).join(", ")}</div>
        <div>Usage — {data.usage.map(line).join(", ")}</div>
      </div>
    </Card>
  );
}

function HistorySection({ equipmentId }: { equipmentId: string }) {
  const { data } = useAsync(() => api.get<SessionRow[]>(`/equipment/${equipmentId}/history`), [equipmentId]);
  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold">Usage history</h3>
      {!data?.length ? (
        <Empty>No past sessions.</Empty>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-text-muted">
            <tr>
              <th className="py-1">Who</th>
              <th>Start</th>
              <th>End</th>
              <th>Ended by</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="py-1">{s.display_name}</td>
                <td>{fmtDateTime(s.started_at)}</td>
                <td>{fmtDateTime(s.ended_at)}</td>
                <td>{s.end_cause ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

export function EquipmentDetail({ byQr }: { byQr?: boolean }) {
  const { id, token } = useParams();
  const { data: eq, error, loading, reload } = useAsync(
    () => api.get<Detail>(byQr ? `/equipment/by-qr/${token}` : `/equipment/${id}`),
    [id, token],
  );

  if (loading) return <Spinner />;
  if (error) return <ErrorNote error={error} />;
  if (!eq) return null;

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-start gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <StatusDot color={eq.status.color} counts={eq.status} />
              <h1 className="text-2xl font-bold text-text">{eq.name}</h1>
              <Badge tone={eq.is_admin ? "brand" : eq.effective_tier === "none" ? "muted" : "brand"}>
                {eq.is_admin ? "admin" : eq.effective_tier}
              </Badge>
              {eq.open_access && <Badge tone="success">open access</Badge>}
              {!eq.enable_gated && <Badge>no-enable</Badge>}
            </div>
            <p className="mt-1 text-sm text-text-muted">
              {eq.class.name} · {eq.location.building} {eq.location.room}
            </p>
            {eq.status.color === "red" && (
              <p className="mt-1 text-sm text-danger">Out of service — an open fatal issue is present.</p>
            )}
          </div>
          <EnableControl row={eq} onChange={reload} />
        </div>
      </Card>

      <QuotaSection equipmentId={eq.id} />
      <ReservationsSection eq={eq} onChange={reload} />
      <IssuesSection eq={eq} onChange={reload} />
      <HistorySection equipmentId={eq.id} />
      <RosterSection eq={eq} />
      {eq.is_admin && <InterlocksSection eq={eq} />}
    </div>
  );
}
