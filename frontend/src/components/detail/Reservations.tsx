import { useState } from "react";

import { ApiError, api } from "../../api/client";
import type { EquipmentDetail, Reservation } from "../../api/types";
import { useAuth } from "../../auth";
import { fmtDateTime, fromLocalInput } from "../../lib/time";
import { useAsync } from "../../lib/useAsync";
import { Button, Card, Empty, ErrorNote, Field, Help, Input, Select, Spinner } from "../ui";

function BookForm({ eq, onBooked }: { eq: EquipmentDetail; onBooked: () => void }) {
  const [start, setStart] = useState("");
  const [dur, setDur] = useState(60);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  if (!eq.can_operate) {
    return (
      <p className="text-xs text-text-muted">
        You are not authorized to reserve this equipment.
        <Help>Ask an admin or a superuser for this item to grant you access.</Help>
      </p>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const startsIso = fromLocalInput(start);
      const endsIso = new Date(new Date(startsIso).getTime() + dur * 60000)
        .toISOString()
        .replace(/\.\d{3}Z$/, "Z");
      await api.post(`/equipment/${eq.id}/reservations`, { starts_at: startsIso, ends_at: endsIso });
      setStart("");
      onBooked();
    } catch (e2) {
      setErr(e2 as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <Field label="Start">
        <Input
          type="datetime-local"
          step={900}
          value={start}
          onChange={(e) => setStart(e.target.value)}
          required
        />
      </Field>
      <Field label="Duration">
        <Select value={dur} onChange={(e) => setDur(Number(e.target.value))}>
          {[15, 30, 60, 90, 120, 180, 240].map((m) => (
            <option key={m} value={m}>
              {m < 60 ? `${m} min` : `${m / 60} h`}
            </option>
          ))}
        </Select>
      </Field>
      <Button type="submit" variant="primary" disabled={busy || !start}>
        Book
      </Button>
      <div className="w-full">
        <ErrorNote error={err} />
      </div>
    </form>
  );
}

export function ReservationsSection({ eq, onChange }: { eq: EquipmentDetail; onChange: () => void }) {
  const { me } = useAuth();
  const { data, loading, error, reload } = useAsync(
    () => api.get<Reservation[]>(`/equipment/${eq.id}/reservations`),
    [eq.id],
  );
  const [cancelErr, setCancelErr] = useState<ApiError | null>(null);

  const cancel = async (r: Reservation) => {
    setCancelErr(null);
    try {
      await api.del(`/reservations/${r.id}`);
      reload();
    } catch (e) {
      setCancelErr(e as ApiError);
    }
  };

  const now = Date.now();
  return (
    <Card>
      <h3 className="mb-3 text-base font-semibold text-text">Reservation calendar</h3>
      <div className="mb-3">
        <BookForm eq={eq} onBooked={() => { reload(); onChange(); }} />
      </div>
      <ErrorNote error={error} />
      <ErrorNote error={cancelErr} />
      {loading ? (
        <Spinner />
      ) : !data?.length ? (
        <Empty>No upcoming reservations.</Empty>
      ) : (
        <ul className="divide-y divide-border">
          {data.map((r) => {
            const mine = me && r.user_id === me.subject;
            const cancelable = new Date(r.starts_at).getTime() > now && (mine || me?.is_admin);
            return (
              <li
                key={r.id}
                className="-mx-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-1.5 text-sm transition-colors hover:bg-surface-muted"
              >
                <span>
                  {fmtDateTime(r.starts_at)} – {fmtDateTime(r.ends_at)}
                  <span className="ml-2 text-xs text-text-muted">
                    {mine ? "you" : r.display_name || r.user_id}
                  </span>
                </span>
                {cancelable && (
                  <Button variant={mine ? "ghost" : "ghost-danger"} onClick={() => cancel(r)}>
                    {mine ? "Cancel" : "Remove"}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
