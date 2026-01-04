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

      login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
          const { user, token } = await AuthAPI.login(email, password);
          set({ user, token, isAuthenticated: true, isLoading: false });
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

      clearError: () => {
        set({ error: null });
      }
    }),
    {
      name: 'whatsapp-crm-auth',
      partialize: (state) => ({ 
        user: state.user, 
        token: state.token,
        isAuthenticated: state.isAuthenticated 
      })
    }
  )
);
