import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthAPI } from '../lib/api';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      maintenance: null,
      maintenanceDismissedKey: null,

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
        set({ user: null, token: null, isAuthenticated: false, error: null });
      },

      refreshCurrentUser: async () => {
        if (!get().token) return null;
        try {
          const user = await AuthAPI.getCurrentUser();
          set({ user, isAuthenticated: true });
          return user;
        } catch (error) {
          return null;
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
