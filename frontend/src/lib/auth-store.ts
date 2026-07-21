/**
 * Zustand auth store for AI Research Assistant.
 * Persists user info to localStorage so sessions survive page refreshes.
 */
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { apiClient, UserResponse } from "./api";

interface AuthState {
  user: UserResponse | null;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    username: string,
    password: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isLoading: false,
      error: null,

      // ── login ────────────────────────────────────────────────────────────
      login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
          const result = await apiClient.login(email, password);
          if (typeof window !== "undefined") {
            localStorage.setItem("access_token", result.tokens.access_token);
            localStorage.setItem("refresh_token", result.tokens.refresh_token);
          }
          // Fetch full user profile (includes created_at, is_active, etc.)
          const user = await apiClient.getCurrentUser();
          set({ user, isLoading: false });
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail ?? "Login failed";
          set({ error: message, isLoading: false });
          throw err;
        }
      },

      // ── register ─────────────────────────────────────────────────────────
      register: async (email, username, password) => {
        set({ isLoading: true, error: null });
        try {
          const result = await apiClient.register(email, username, password);
          if (typeof window !== "undefined") {
            localStorage.setItem("access_token", result.tokens.access_token);
            localStorage.setItem("refresh_token", result.tokens.refresh_token);
          }
          const user = await apiClient.getCurrentUser();
          set({ user, isLoading: false });
        } catch (err: unknown) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail ?? "Registration failed";
          set({ error: message, isLoading: false });
          throw err;
        }
      },

      // ── logout ───────────────────────────────────────────────────────────
      logout: async () => {
        try {
          await apiClient.logout();
        } catch {
          // Ignore logout API errors — always clear local state
        }
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
        }
        set({ user: null, error: null });
      },

      // ── checkAuth ────────────────────────────────────────────────────────
      checkAuth: async () => {
        if (typeof window === "undefined") return;
        const token = localStorage.getItem("access_token");
        if (!token) {
          set({ user: null });
          return;
        }
        try {
          const user = await apiClient.getCurrentUser();
          set({ user });
        } catch {
          // Token invalid or expired — clear everything
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          set({ user: null });
        }
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() =>
        typeof window !== "undefined"
          ? localStorage
          : {
              getItem: () => null,
              setItem: () => undefined,
              removeItem: () => undefined,
            },
      ),
      // Only persist the user object — tokens stay in raw localStorage
      partialize: (state) => ({ user: state.user }),
    },
  ),
);
