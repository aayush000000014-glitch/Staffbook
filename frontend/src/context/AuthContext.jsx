import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, TOKEN_KEY } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ loading: true, user: null, business: null });

  const refresh = useCallback(async () => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      setState({ loading: false, user: null, business: null });
      return;
    }
    try {
      const { data } = await api.get("/auth/me");
      setState({ loading: false, user: data.user, business: data.business });
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setState({ loading: false, user: null, business: null });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const signIn = async (token) => {
    localStorage.setItem(TOKEN_KEY, token);
    await refresh();
  };

  const signOut = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      /* token may already be invalid */
    }
    localStorage.removeItem(TOKEN_KEY);
    setState({ loading: false, user: null, business: null });
  };

  return <AuthCtx.Provider value={{ ...state, refresh, signIn, signOut }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

export const homeFor = (user, business) => {
  if (!user) return "/login";
  if (user.role === "super_admin") return "/admin";
  if (user.role === "staff") return "/me";
  if (business && !business.onboarded) return "/onboarding";
  return "/dashboard";
};
