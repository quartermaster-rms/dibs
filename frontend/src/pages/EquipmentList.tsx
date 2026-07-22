import { useState } from "react";
import { Link } from "react-router-dom";

import { api, qs } from "../api/client";
import type { EquipmentRow, Tier } from "../api/types";
import { EnableControl } from "../components/EnableControl";
import { Badge, Card, Empty, ErrorNote, Input, Spinner, StatusDot } from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

const tierTone: Record<Tier, "muted" | "brand"> = { none: "muted", user: "brand", superuser: "brand" };

function Row({ row, onChange }: { row: EquipmentRow; onChange: () => void }) {
  return (
    <Card className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <StatusDot color={row.status.color} counts={row.status} />
      <div className="min-w-[12rem] flex-1">
        <Link to={`/equipment/${row.id}`} className="font-medium text-text hover:text-brand">
          {row.name}
        </Link>
        <div className="text-xs text-text-muted">
          {row.class_name} · {row.location.building} {row.location.room}
        </div>
      </div>
      <Badge tone={row.is_admin ? "brand" : tierTone[row.effective_tier]}>
        {row.is_admin ? "admin" : row.effective_tier}
      </Badge>
      <div className="min-w-[9rem] text-xs text-text-muted">
        {row.current_holder ? (
          <span className="text-warning">In use · {row.current_holder.display_name}</span>
        ) : row.next_reservation ? (
          <span>Next: {fmtDateTime(row.next_reservation.starts_at)}</span>
        ) : (
          <span>Free</span>
        )}
      </div>
      <EnableControl row={row} onChange={onChange} />
    </Card>
  );
}

export function EquipmentList() {
  const [q, setQ] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [enabledByMe, setEnabledByMe] = useState(false);
  const { data, error, loading, reload } = useAsync(
    () =>
      api.get<EquipmentRow[]>(
        "/equipment" + qs({ q, authorized, enabled_by_me: enabledByMe }),
      ),
    [q, authorized, enabledByMe],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search equipment, class, or location…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-sm"
          aria-label="Search equipment"
        />
        <label className="flex items-center gap-1.5 text-sm text-text">
          <input type="checkbox" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} />
          Equipment I&apos;m authorized to
        </label>
        <label className="flex items-center gap-1.5 text-sm text-text">
          <input
            type="checkbox"
            checked={enabledByMe}
            onChange={(e) => setEnabledByMe(e.target.checked)}
          />
          Equipment I have enabled
        </label>
      </div>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No equipment matches.</Empty>
      ) : (
        <div className="space-y-2">
          {data.map((row) => (
            <Row key={row.id} row={row} onChange={reload} />
          ))}
        </div>
      )}
    </div>
  );
}
