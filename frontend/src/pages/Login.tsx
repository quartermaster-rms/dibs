import { useState } from "react";

import { useAuth } from "../auth";
import { Button, Card, ErrorNote, Field, Input } from "../components/ui";

export function Login() {
  const { config, stubLogin } = useAuth();
  const [subject, setSubject] = useState("");
  const [groups, setGroups] = useState("");
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);

  const stub = config?.stub_login ?? true;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await stubLogin(
        subject.trim(),
        groups.split(",").map((g) => g.trim()).filter(Boolean),
      );
    } catch (err) {
      setError(err as Error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted p-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-2xl font-bold text-brand">dibs</h1>
        <p className="mb-4 text-sm text-text-muted">Equipment reservations & interlocks.</p>
        {stub ? (
          <form onSubmit={submit} className="space-y-3">
            <p className="text-xs text-text-muted">Dev sign-in (stub identity).</p>
            <Field label="Username">
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} required autoFocus />
            </Field>
            <Field label="Groups" hint="comma-separated, e.g. admin-dibs, group-eng">
              <Input value={groups} onChange={(e) => setGroups(e.target.value)} placeholder="group-eng" />
            </Field>
            <ErrorNote error={error} />
            <Button type="submit" variant="primary" className="w-full" disabled={busy || !subject.trim()}>
              Sign in
            </Button>
          </form>
        ) : (
          <a href="/api/auth/login">
            <Button variant="primary" className="w-full">
              Sign in with SSO
            </Button>
          </a>
        )}
      </Card>
    </div>
  );
}
