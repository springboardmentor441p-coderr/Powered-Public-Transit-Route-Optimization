'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, authApi } from '@/lib/api';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'operator' | 'viewer';
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; role?: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
  fetchUser: () => Promise<void>;
  updateUser: (data: Partial<User>) => Promise<void>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login(email, password);
          const { access_token, refresh_token } = response.data;

          // Store tokens
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);

          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });

          // Fetch user profile
          await get().fetchUser();
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Login failed';
          set({ error: message, isLoading: false, isAuthenticated: false });
          throw error;
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          await authApi.register(data);
          set({ isLoading: false });
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Registration failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        const refreshToken = get().refreshToken;
        if (refreshToken) {
          try {
            await authApi.logout(refreshToken);
          } catch {
            // Ignore logout errors
          }
        }

        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      refreshAccessToken: async () => {
        const refreshToken = get().refreshToken;
        if (!refreshToken) {
          get().logout();
          return;
        }

        try {
          const response = await authApi.refresh(refreshToken);
          const { access_token, refresh_token: newRefreshToken } = response.data;

          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', newRefreshToken);

          set({
            accessToken: access_token,
            refreshToken: newRefreshToken,
          });
        } catch {
          get().logout();
        }
      },

      fetchUser: async () => {
        try {
          const response = await authApi.me();
          set({ user: response.data, isAuthenticated: true });
        } catch {
          set({ user: null, isAuthenticated: false });
        }
      },

      updateUser: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.updateMe(data);
          set({ user: response.data, isLoading: false });
        } catch (error: any) {
          const message = error.response?.data?.detail || 'Update failed';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      clearError: () => set({ error: null }),
      setLoading: (loading: boolean) => set({ isLoading: loading }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

// Initialize auth on app load
if (typeof window !== 'undefined') {
  const storedAccessToken = localStorage.getItem('access_token');
  const storedRefreshToken = localStorage.getItem('refresh_token');

  if (storedAccessToken && storedRefreshToken) {
    useAuthStore.setState({
      accessToken: storedAccessToken,
      refreshToken: storedRefreshToken,
      isAuthenticated: true,
    });

    // Fetch user profile
    useAuthStore.getState().fetchUser();
  }
}