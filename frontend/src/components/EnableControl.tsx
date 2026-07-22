import { useState } from "react";

import { ApiError, api } from "../api/client";
import type { EquipmentRow } from "../api/types";
import { useAuth } from "../auth";
import { Button, ErrorNote, Help, helpFor } from "./ui";

export function EnableControl({ row, onChange }: { row: EquipmentRow; onChange: () => void }) {
  const { me } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  // No Enable path on a no-enable item (capability-aware: control absent).
  if (!row.enable_gated) return <span className="text-xs text-text-muted">No interlock</span>;

  const call = async (action: "enable" | "disable") => {
    setBusy(true);
    setErr(null);
    try {
      await api.post(`/equipment/${row.id}/${action}`);
      onChange();
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  const holder = row.current_holder;
  const iAmHolder = holder && me && holder.subject === me.subject;

  let control;
  if (iAmHolder) {
    control = (
      <Button variant="danger" disabled={busy} onClick={() => call("disable")}>
        Disable
      </Button>
    );
  } else if (holder) {
    control = me?.is_admin ? (
      <Button variant="danger" disabled={busy} onClick={() => call("disable")}>
        Force close · {holder.display_name}
      </Button>
    ) : (
      <span className="text-xs text-text-muted">
        In use by {holder.display_name}
        <Help>{helpFor("equipment_in_use")}</Help>
      </span>
    );
  } else {
    const blockedByRed = row.status.color === "red" && !me?.is_admin;
    const canEnable = row.can_operate && !blockedByRed;
    control = (
      <span className="inline-flex items-center gap-1">
        <Button variant="primary" disabled={!canEnable || busy} onClick={() => call("enable")}>
          Enable
        </Button>
        {!row.can_operate && (
          <span className="text-xs text-text-muted">
            Not authorized
            <Help>{helpFor("forbidden")}</Help>
          </span>
        )}
        {row.can_operate && blockedByRed && (
          <span className="text-xs text-danger">
            Red
            <Help>{helpFor("fatal_fault_open")}</Help>
          </span>
        )}
      </span>
    );
  }

  return (
    <div className="space-y-1">
      {control}
      <ErrorNote error={err} />
    </div>
  );
}
