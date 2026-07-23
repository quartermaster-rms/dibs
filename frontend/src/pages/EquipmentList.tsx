import { useState } from "react";
import { Link } from "react-router-dom";

import { api, qs } from "../api/client";
import type { EquipmentRow, Tier } from "../api/types";
import { EnableControl } from "../components/EnableControl";
import {
  Badge,
  Card,
  CheckboxField,
  Empty,
  ErrorNote,
  PageHeading,
  SearchInput,
  Spinner,
  StatusDot,
} from "../components/ui";
import { fmtDateTime } from "../lib/time";
import { useAsync } from "../lib/useAsync";

const tierTone: Record<Tier, "muted" | "brand"> = {
  none: "muted",
  user: "brand",
  superuser: "brand",
};

function Row({ row, onChange }: { row: EquipmentRow; onChange: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors hover:bg-surface-muted">
      <StatusDot color={row.status.color} counts={row.status} />
      <div className="min-w-[12rem] flex-1">
        <Link
          to={`/equipment/${row.id}`}
          className="rounded font-medium text-text transition-colors hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          {row.name}
        </Link>
        <div className="text-xs text-text-muted">
          {row.class_name} · {row.location.building} {row.location.room}
        </div>
      </div>
      <Badge tone={row.is_admin ? "brand" : tierTone[row.effective_tier]}>
        {row.is_admin ? "admin" : row.effective_tier}
      </Badge>
      <div className="min-w-[9rem] space-y-0.5 text-xs text-text-muted">
        {row.current_holder && (
          <div className="text-warning">In use · {row.current_holder.display_name}</div>
        )}
        {row.next_reservation && <div>Next: {fmtDateTime(row.next_reservation.starts_at)}</div>}
        {!row.current_holder && !row.next_reservation && <div>Free</div>}
      </div>
      <EnableControl row={row} onChange={onChange} />
    </div>
  );
}

export function EquipmentList() {
  const [q, setQ] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [enabledByMe, setEnabledByMe] = useState(false);
  const { data, error, loading, reload } = useAsync(
    () => api.get<EquipmentRow[]>("/equipment" + qs({ q, authorized, enabled_by_me: enabledByMe })),
    [q, authorized, enabledByMe],
  );

  return (
    <div className="space-y-4">
      <PageHeading title="Equipment" subtitle={data ? `${data.length} shown` : undefined} />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <SearchInput
          placeholder="Search equipment, class, or location…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onClear={() => setQ("")}
          className="w-full max-w-sm"
          aria-label="Search equipment"
        />
        <CheckboxField
          label="Authorized to me"
          checked={authorized}
          onChange={(e) => setAuthorized(e.target.checked)}
        />
        <CheckboxField
          label="Enabled by me"
          checked={enabledByMe}
          onChange={(e) => setEnabledByMe(e.target.checked)}
        />
      </div>
      <ErrorNote error={error} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No equipment matches.</Empty>
      ) : (
        <Card className="divide-y divide-border overflow-hidden p-0">
          {data.map((row) => (
            <Row key={row.id} row={row} onChange={reload} />
          ))}
        </Card>
      )}
    </div>
  );
}
