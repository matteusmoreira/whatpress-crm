import React, { useEffect, useMemo } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuthStore } from '../../store/authStore';
import { useTheme } from '../../context/ThemeContext';
import { cn } from '../../lib/utils';

const MainLayout = () => {
  const { isAuthenticated, user, refreshCurrentUser, maintenance, maintenanceDismissedKey, dismissMaintenance } = useAuthStore();
  const { theme } = useTheme();

  useEffect(() => {
    refreshCurrentUser?.();
  }, [refreshCurrentUser]);

  const maintenanceKey = useMemo(() => {
    if (!maintenance?.enabled) return null;
    const k = String(maintenance?.updatedAt || '').trim();
    return k || 'enabled';
  }, [maintenance]);

  const showMaintenance = useMemo(() => {
    if (!isAuthenticated) return false;
    if (user?.role === 'superadmin') return false;
    if (!maintenance?.enabled) return false;
    if (!maintenanceKey) return true;
    return maintenanceKey !== maintenanceDismissedKey;
  }, [isAuthenticated, maintenance, maintenanceDismissedKey, maintenanceKey, user?.role]);

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

      {showMaintenance && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60" onClick={() => dismissMaintenance?.()} />
          <div
            className={cn(
              "relative w-full max-w-2xl rounded-3xl border shadow-2xl overflow-hidden",
              theme === 'dark'
                ? "backdrop-blur-xl bg-gradient-to-br from-white/15 to-white/5 border-white/20"
                : "bg-white border-slate-200"
            )}
          >
            <div className={cn(
              "px-6 py-5 flex items-start justify-between gap-4",
              theme === 'dark' ? "border-b border-white/10" : "border-b border-slate-200"
            )}>
              <div>
                <div className={cn("text-xl font-bold", theme === 'dark' ? "text-white" : "text-slate-900")}>
                  Sistema em manutenção
                </div>
                <div className={cn("text-sm mt-1", theme === 'dark' ? "text-white/70" : "text-slate-600")}>
                  Algumas funcionalidades podem ficar indisponíveis
                </div>
              </div>
              <button
                onClick={() => dismissMaintenance?.()}
                className={cn(
                  "px-4 py-2 rounded-xl font-medium transition-all active:scale-95",
                  theme === 'dark'
                    ? "bg-white/10 hover:bg-white/20 text-white border border-white/20"
                    : "bg-slate-100 hover:bg-slate-200 text-slate-800"
                )}
              >
                Entendi
              </button>
            </div>

            <div className="px-6 py-6">
              {maintenance?.messageHtml ? (
                <div
                  className={cn(
                    "prose max-w-none",
                    theme === 'dark'
                      ? "prose-invert prose-a:text-emerald-300"
                      : "prose-a:text-emerald-700"
                  )}
                  dangerouslySetInnerHTML={{ __html: maintenance.messageHtml }}
                />
              ) : (
                <div className={cn(theme === 'dark' ? "text-white/80" : "text-slate-700")}>
                  Estamos realizando manutenção no sistema. Tente novamente em instantes.
                </div>
              )}

              {Array.isArray(maintenance?.attachments) && maintenance.attachments.length > 0 && (
                <div className="mt-6">
                  <div className={cn("text-sm font-semibold mb-2", theme === 'dark' ? "text-white" : "text-slate-900")}>
                    Anexos
                  </div>
                  <div className="space-y-2">
                    {maintenance.attachments.map((a) => (
                      <a
                        key={a.url}
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className={cn(
                          "block px-4 py-3 rounded-2xl border transition-colors truncate",
                          theme === 'dark'
                            ? "bg-white/5 border-white/10 hover:bg-white/10 text-emerald-200"
                            : "bg-slate-50 border-slate-200 hover:bg-slate-100 text-emerald-700"
                        )}
                      >
                        {a.name || a.url}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MainLayout;
