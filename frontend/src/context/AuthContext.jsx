import { createContext, useCallback, useContext, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { authApi } from "../services/endpoints";

const AuthContext = createContext(null);

/**
 * Session state comes from the backend (/auth/me) – the browser never sees a token.
 * The backend enforces expiry; the frontend just reflects it (and re-checks every minute).
 */
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await authApi.me();
      } catch (e) {
        if (e.response?.status === 401) return null;
        throw e;
      }
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
  });

  const clear = useCallback(() => {
    queryClient.setQueryData(["me"], null);
    queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" && q.queryKey[0] !== "school" });
  }, [queryClient]);

  useEffect(() => {
    const onUnauthorized = (e) => {
      if (queryClient.getQueryData(["me"])) {
        toast.error(e.detail?.code === "session_expired" ? "Your session has ended. Please sign in again." : "Please sign in again.", { id: "session" });
      }
      clear();
    };
    window.addEventListener("sams:unauthorized", onUnauthorized);
    return () => window.removeEventListener("sams:unauthorized", onUnauthorized);
  }, [clear, queryClient]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* session may already be gone */
    }
    clear();
    toast.success("You have been signed out.");
  }, [clear]);

  const refresh = useCallback(() => queryClient.invalidateQueries({ queryKey: ["me"] }), [queryClient]);

  const value = useMemo(
    () => ({ user: meQuery.data ?? null, loading: meQuery.isLoading, refresh, logout, clear }),
    [meQuery.data, meQuery.isLoading, refresh, logout, clear],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
