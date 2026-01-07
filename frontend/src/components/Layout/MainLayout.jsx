import React, { useEffect } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuthStore } from '../../store/authStore';
import { useTheme } from '../../context/ThemeContext';
import { cn } from '../../lib/utils';

const MainLayout = () => {
  const { isAuthenticated, user, refreshCurrentUser } = useAuthStore();
  const { theme } = useTheme();

  useEffect(() => {
    refreshCurrentUser?.();
  }, [refreshCurrentUser]);

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace />;
  }

  return (
    <div className={cn(
      "h-[100dvh] flex overflow-hidden transition-colors duration-300",
      theme === 'dark'
        ? "bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-900"
        : "bg-slate-50"
    )}>
      <Sidebar />
      <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
};

export default MainLayout;
