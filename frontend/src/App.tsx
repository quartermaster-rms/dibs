import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth";
import { Button, cx } from "./components/ui";
import { tzLabel } from "./lib/time";
import { AuditPage } from "./pages/Audit";
import { EquipmentDetail } from "./pages/EquipmentDetail";
import { EquipmentList } from "./pages/EquipmentList";
import { IssueDetail } from "./pages/IssueDetail";
import { IssuesPage } from "./pages/Issues";
import { Login } from "./pages/Login";
import { NotificationsPage } from "./pages/Notifications";
import { PeoplePage } from "./pages/People";
import { SettingsPage } from "./pages/Settings";
import { useTheme } from "./theme";

function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      end={to === "/"}
      className={({ isActive }) =>
        cx(
          "rounded-control px-3 py-1.5 text-sm font-medium",
          isActive ? "bg-brand-soft text-brand" : "text-text-muted hover:bg-surface-muted",
        )
      }
    >
      {children}
    </NavLink>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const { me, logout } = useAuth();
  const { theme, toggle } = useTheme();
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-40 border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-2">
          <NavLink to="/" className="mr-2 text-lg font-bold text-brand">
            dibs
          </NavLink>
          <nav className="flex flex-1 flex-wrap items-center gap-1">
            <NavItem to="/">Equipment</NavItem>
            <NavItem to="/issues">Issues</NavItem>
            <NavItem to="/people">People</NavItem>
            <NavItem to="/notifications">Inbox</NavItem>
            {me?.is_admin && <NavItem to="/settings">Settings</NavItem>}
            {me?.is_admin && <NavItem to="/audit">Audit</NavItem>}
          </nav>
          <span className="hidden text-xs text-text-muted sm:inline" title="Times shown in this zone">
            {tzLabel()}
          </span>
          <Button variant="ghost" onClick={toggle} aria-label="Toggle theme">
            {theme === "dark" ? "☀" : "☾"}
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-text">{me?.display_name}</span>
            {me?.is_admin && <span className="text-xs text-brand">admin</span>}
            <Button variant="ghost" onClick={() => logout()}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export default function App() {
  const { me, loading } = useAuth();
  if (loading) return <div className="p-8 text-text-muted">Loading…</div>;
  if (!me) return <Login />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<EquipmentList />} />
        <Route path="/equipment/:id" element={<EquipmentDetail />} />
        <Route path="/qr/:token" element={<EquipmentDetail byQr />} />
        <Route path="/issues" element={<IssuesPage />} />
        <Route path="/issues/:id" element={<IssueDetail />} />
        <Route path="/people" element={<PeoplePage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        {me.is_admin && <Route path="/settings" element={<SettingsPage />} />}
        {me.is_admin && <Route path="/audit" element={<AuditPage />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
