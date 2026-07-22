import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AuthProvider } from "../auth";
import { ThemeProvider } from "../theme";

export interface Route {
  match: RegExp | string;
  method?: string;
  respond: (init: RequestInit, path: string) => { status?: number; body?: unknown };
}

export function installFetch(routes: Route[]) {
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, "").replace(/^\/api/, "");
    const method = (init?.method || "GET").toUpperCase();
    for (const r of routes) {
      const matched =
        typeof r.match === "string" ? path === r.match || path.startsWith(r.match) : r.match.test(path);
      if (matched && (!r.method || r.method.toUpperCase() === method)) {
        const res = r.respond(init || {}, path) || {};
        const status = res.status ?? 200;
        const body = res.body === undefined ? "" : JSON.stringify(res.body);
        return new Response(status === 204 ? null : body, {
          status,
          headers: { "content-type": "application/json" },
        });
      }
    }
    return new Response(JSON.stringify({ error: { code: "not_found", message: "not found" } }), {
      status: 404,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
}

interface Me {
  subject: string;
  display_name?: string;
  email?: string;
  groups?: string[];
  is_admin?: boolean;
  is_sysadmin?: boolean;
}

export function meRoutes(me: Me | null, extra: Route[] = []): Route[] {
  const base: Route[] = [
    {
      match: "/config",
      respond: () => ({ body: { platform_tz: "America/Los_Angeles", auth_mode: "stub", stub_login: true } }),
    },
    {
      match: "/me",
      method: "GET",
      respond: () =>
        me
          ? {
              body: {
                subject: me.subject,
                display_name: me.display_name ?? me.subject,
                email: me.email ?? "",
                groups: me.groups ?? [],
                is_admin: me.is_admin ?? false,
                is_sysadmin: me.is_sysadmin ?? false,
                csrf_token: "csrf",
              },
            }
          : { status: 401, body: { error: { code: "unauthenticated", message: "no" } } },
    },
    ...extra,
  ];
  return base;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function mkRow(overrides: Record<string, any> = {}): any {
  return {
    id: "e1",
    name: "Lathe",
    class_id: "c1",
    class_name: "Lathes",
    location: { id: "l1", building: "B", room: "1" },
    photo_path: null,
    qr_token: "t",
    open_use: false,
    requires_enable: true,
    open_access: false,
    enable_gated: true,
    status: { color: "green", open_fatal: 0, open_warning: 0 },
    effective_tier: "user",
    is_admin: false,
    can_operate: true,
    current_holder: null,
    next_reservation: null,
    node_count: 0,
    ...overrides,
  };
}

export function renderWith(ui: ReactElement, me: Me | null, extra: Route[] = [], path = "/") {
  installFetch(meRoutes(me, extra));
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </ThemeProvider>,
  );
}
