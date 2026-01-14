import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthAPI, MaintenanceAPI } from '../lib/api';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      isBootstrapping: false,
      error: null,
      maintenance: null,
      maintenanceDismissedKey: null,

      initAuth: async () => {
        if (get().isBootstrapping) return null;
        set({ isBootstrapping: true });
        try {
          const hasToken =
            Boolean(get().token) ||
            (() => {
              try {
                const raw = localStorage.getItem('whatsapp-crm-auth');
                if (!raw) return false;
                const parsed = JSON.parse(raw);
                return Boolean(parsed?.state?.token);
              } catch {
                return false;
              }
            })();

          if (!hasToken) {
            set({ user: null, token: null, isAuthenticated: false, maintenance: null, maintenanceDismissedKey: null });
            return null;
          }

          const user = await AuthAPI.getCurrentUser();
          if (user) {
            set({ user, isAuthenticated: true });
          }
          return user || null;
        } catch (error) {
          if (error?.response?.status === 401) {
            set({ user: null, token: null, isAuthenticated: false, maintenance: null, maintenanceDismissedKey: null });
          }
          return null;
        } finally {
          set({ isBootstrapping: false });
        }
      },

      login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
          const { user, token, maintenance } = await AuthAPI.login(email, password);
          const normalizedMaintenance = maintenance?.enabled ? maintenance : null;
          set({ user, token, maintenance: normalizedMaintenance, isAuthenticated: true, isLoading: false });
          return user;
        } catch (error) {
          const message = error.response?.data?.detail || 'Erro ao fazer login';
          set({ error: message, isLoading: false });
          throw new Error(message);
        }
      },

      logout: () => {
        const token = get().token;
        if (token) {
          AuthAPI.logout().catch(() => null);
        }
        set({ user: null, token: null, isAuthenticated: false, error: null, maintenance: null, maintenanceDismissedKey: null });
      },

      refreshCurrentUser: async () => {
        if (!get().token) return null;
        try {
          const user = await AuthAPI.getCurrentUser();
          set({ user, isAuthenticated: true });
          return user;
        } catch (error) {
          if (error?.response?.status === 401) {
            set({ user: null, token: null, isAuthenticated: false, maintenance: null, maintenanceDismissedKey: null });
          }
          return null;
        }
      },

      refreshMaintenance: async () => {
        if (!get().token) return null;
        try {
          const maintenance = await MaintenanceAPI.get();
          const normalizedMaintenance = maintenance?.enabled ? maintenance : null;
          set({ maintenance: normalizedMaintenance });
          return normalizedMaintenance;
        } catch (error) {
          return get().maintenance || null;
        }
      },

      updateCurrentUser: async (data) => {
        if (!get().token) return null;
        const user = await AuthAPI.updateCurrentUser(data);
        set({ user });
        return user;
      },

      dismissMaintenance: () => {
        const m = get().maintenance;
        const key = String(m?.updatedAt || '').trim() || (m?.enabled ? 'enabled' : '');
        if (!key) {
          set({ maintenance: null });
          return;
        }
        set({ maintenanceDismissedKey: key });
      },

      clearError: () => {
        set({ error: null });
      }
    }),
    {
      name: 'whatsapp-crm-auth',
      partialize: (state) => ({ 
        user: state.user, 
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        maintenanceDismissedKey: state.maintenanceDismissedKey
      })
    }
  )
);
