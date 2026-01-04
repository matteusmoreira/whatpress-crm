import React from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuthStore } from '../../store/authStore';
import { useTheme } from '../../context/ThemeContext';
import { cn } from '../../lib/utils';

const MainLayout = () => {
  const { isAuthenticated, user } = useAuthStore();
  const { theme } = useTheme();

  if (!isAuthenticated) {
    return <Navigate to="/sign-in" replace />;
  }

  return (
    <div className={cn(
      "min-h-screen flex transition-colors duration-300",
      theme === 'dark' 
        ? "bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-900" 
        : "bg-gradient-to-br from-slate-100 via-emerald-50 to-teal-50"
    )}>
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
};

export default MainLayout;
