import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api } from "./api/client";
import type { Me } from "./api/types";
import { setTz } from "./lib/time";

interface ClientConfig {
  platform_tz: string;
  auth_mode: string;
  stub_login: boolean;
}

interface AuthState {
  me: Me | null;
  config: ClientConfig | null;
  loading: boolean;
  refresh: () => Promise<void>;
  stubLogin: (subject: string, groups: string[], name?: string, email?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>(null as unknown as AuthState);

export function useAuth() {
  return useContext(AuthCtx);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [config, setConfig] = useState<ClientConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.get<Me>("/me"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      else throw e;
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const cfg = await api.get<ClientConfig>("/config");
        setConfig(cfg);
        setTz(cfg.platform_tz);
      } catch {
        /* config is best-effort */
      }
      await refresh().catch(() => setMe(null));
      setLoading(false);
    })();
  }, [refresh]);

  const stubLogin = async (subject: string, groups: string[], name?: string, email?: string) => {
    await api.post("/auth/stub-login", {
      subject,
      groups,
      display_name: name || subject,
      email: email || `${subject}@example.edu`,
    });
    await refresh();
  };

  const logout = async () => {
    await api.post("/auth/logout");
    setMe(null);
  };

  return (
    <AuthCtx.Provider value={{ me, config, loading, refresh, stubLogin, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}
