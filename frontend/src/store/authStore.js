import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AuthRepository } from '../lib/storage';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
          const user = await AuthRepository.login(email, password);
          set({ user, isAuthenticated: true, isLoading: false });
          return user;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          throw error;
        }
      },

      logout: () => {
        set({ user: null, isAuthenticated: false, error: null });
      },

      clearError: () => {
        set({ error: null });
      }
    }),
    {
      name: 'whatsapp-crm-auth',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated })
    }
  )
);
