import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Settings,
  Users,
  ChevronLeft,
  LogOut,
  Menu,
  X,
  Building2,
  Plug,
  Search,
  User,
  Bot,
  CreditCard,
  Wrench,
  PanelLeftClose,
  PanelLeft,
  Workflow
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useAppStore } from '../../store/appStore';
import { useTheme } from '../../context/ThemeContext';
import { cn } from '../../lib/utils';
import SearchModal from '../SearchModal';
import ThemeToggle from '../ThemeToggle';
import { toast } from '../ui/glass-toaster';

const Sidebar = () => {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar, conversations, brandName, selectedConversation, setSelectedConversation } = useAppStore();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [showSearch, setShowSearch] = useState(false);

  const handleLogout = () => {
    logout();
    toast.success('Até logo!', { description: 'Você foi desconectado com sucesso.' });
    navigate('/sign-in');
  };

  const isSuperAdmin = user?.role === 'superadmin';
  const canManageConnections = user?.role === 'admin';

  const navItems = isSuperAdmin
    ? [
      { to: '/superadmin', icon: LayoutDashboard, label: 'Dashboard', end: true },
      { to: '/superadmin/tenants', icon: Building2, label: 'Tenants' },
      { to: '/superadmin/plans', icon: CreditCard, label: 'Planos' },
      { to: '/superadmin/users', icon: Users, label: 'Usuários' },
      { to: '/superadmin/maintenance', icon: Wrench, label: 'Manutenção' },
      { to: '/app/automations', icon: Bot, label: 'Disparos' },
    ]
    : [
      { to: '/app/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/app/inbox', icon: MessageSquare, label: 'Bate Papo' },
      { to: '/app/contacts', icon: Users, label: 'Contatos' },
      { to: '/app/automations', icon: Bot, label: 'Disparos' },
      { to: '/app/flows', icon: Workflow, label: 'Fluxos' },
      ...(canManageConnections ? [{ to: '/app/settings/connections', icon: Plug, label: 'Conexões' }] : []),
      { to: '/app/settings', icon: Settings, label: 'Configurações', end: true },
    ];

  const handleSelectConversation = (conv) => {
    navigate('/app/inbox');
  };

  return (
    <>
      {/* Search Modal */}
      <SearchModal
        isOpen={showSearch}
        onClose={() => setShowSearch(false)}
        conversations={conversations}
        onSelectConversation={handleSelectConversation}
      />

      {/* Mobile toggle button */}
      <button
        onClick={() => {
          if (!sidebarCollapsed) {
            toggleSidebar();
            return;
          }
          const isInbox = location.pathname.startsWith('/app/inbox');
          const hasOpenConversation = Boolean(isInbox && selectedConversation?.id);
          if (hasOpenConversation) {
            setSelectedConversation(null);
            return;
          }
          toggleSidebar();
        }}
        className="lg:hidden fixed top-4 left-4 z-50 p-2.5 rounded-lg bg-emerald-600 text-white shadow-lg transition-all duration-200 ease-out hover:bg-emerald-500 active:scale-95 active:bg-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/60"
      >
        {(() => {
          const isInbox = location.pathname.startsWith('/app/inbox');
          const hasOpenConversation = Boolean(isInbox && selectedConversation?.id);
          const mode = !sidebarCollapsed ? 'close' : hasOpenConversation ? 'back' : 'menu';
          const base = 'absolute inset-0 w-6 h-6 transition-all duration-200 ease-out';
          const hidden = 'opacity-0 scale-95 translate-x-1';
          const visible = 'opacity-100 scale-100 translate-x-0';
          return (
            <div className="relative w-6 h-6">
              <ChevronLeft className={cn(base, mode === 'back' ? visible : hidden)} />
              <Menu className={cn(base, mode === 'menu' ? visible : hidden)} />
              <X className={cn(base, mode === 'close' ? visible : hidden)} />
            </div>
          );
        })()}
      </button>

      {/* Overlay for mobile */}
      {!sidebarCollapsed && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed lg:static inset-y-0 left-0 z-40',
          'w-72 h-full overflow-y-auto',
          'border-r',
          'flex flex-col',
          'transition-all duration-300 ease-in-out',
          sidebarCollapsed ? '-translate-x-full lg:translate-x-0 lg:w-20' : 'translate-x-0',
          theme !== 'light' && 'backdrop-blur-xl',
          theme === 'dark'
            ? 'bg-gradient-to-b from-emerald-900/90 to-emerald-950/95 border-white/10'
            : theme === 'light'
              ? 'bg-white border-slate-200 shadow-lg'
              : theme === 'black'
                ? 'bg-gradient-to-b from-zinc-950 to-black border-white/5'
                : theme === 'purple'
                  ? 'bg-gradient-to-b from-purple-950/90 to-indigo-950/95 border-purple-500/20'
                  : 'bg-gradient-to-b from-emerald-900/90 to-emerald-950/95 border-white/10'
        )}
      >
        {/* Logo */}
        <div className={cn(
          "p-6 border-b",
          theme === 'dark' ? 'border-white/10' : 'border-slate-200'
        )}>
          <div className={cn(
            sidebarCollapsed
              ? "flex flex-col items-center gap-3"
              : "flex items-center justify-between gap-3"
          )}>
            {!sidebarCollapsed && (
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                  <MessageSquare className="w-6 h-6 text-white" />
                </div>
                <span className={cn(
                  "text-xl font-bold",
                  theme === 'dark' ? 'text-white' : 'text-slate-800'
                )}>{brandName || 'WhatsApp CRM'}</span>
              </div>
            )}
            {sidebarCollapsed && (
              <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
                <MessageSquare className="w-6 h-6 text-white" />
              </div>
            )}
            {/* Collapse/Expand button - always visible on desktop */}
            <button
              onClick={toggleSidebar}
              className={cn(
                "hidden lg:flex p-2 rounded-lg transition-all",
                theme === 'dark'
                  ? 'hover:bg-white/10 text-white/60 hover:text-white'
                  : 'hover:bg-slate-100 text-slate-500 hover:text-slate-800',
                sidebarCollapsed && "mt-1"
              )}
              title={sidebarCollapsed ? "Expandir menu" : "Retrair menu"}
            >
              {sidebarCollapsed ? (
                <PanelLeft className="w-5 h-5" />
              ) : (
                <PanelLeftClose className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* Search Button */}
        {!isSuperAdmin && (
          <div className={cn(
            "p-4 border-b",
            theme === 'dark' ? 'border-white/10' : 'border-slate-200'
          )}>
            <button
              onClick={() => setShowSearch(true)}
              className={cn(
                sidebarCollapsed
                  ? 'mx-auto grid h-12 w-12 place-items-center rounded-xl'
                  : 'flex items-center gap-3 w-full px-4 py-3 rounded-xl',
                'group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/60',
                'transition-colors duration-300 ease-in-out',
                theme === 'dark'
                  ? 'bg-white/5 hover:bg-white/10 text-white/70 hover:text-white'
                  : 'bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900'
              )}
              aria-label="Buscar"
              title={sidebarCollapsed ? 'Buscar' : undefined}
            >
              <Search className={cn(
                "w-5 h-5 group-hover:scale-110 transition-transform duration-300 ease-in-out",
                !sidebarCollapsed && "flex-shrink-0"
              )} />
              {!sidebarCollapsed && (
                <>
                  <span className="flex-1 text-left text-sm">Buscar...</span>
                  <kbd className={cn(
                    "hidden lg:inline px-1.5 py-0.5 rounded text-xs",
                    theme === 'dark' ? 'bg-white/10' : 'bg-slate-200'
                  )}>⌘K</kbd>
                </>
              )}
            </button>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              aria-label={item.label}
              title={sidebarCollapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  sidebarCollapsed
                    ? 'mx-auto grid h-12 w-12 place-items-center rounded-xl'
                    : 'flex items-center gap-3 px-4 py-3 rounded-xl',
                  'group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/60',
                  'transition-colors duration-300 ease-in-out',
                  isActive
                    ? theme === 'dark'
                      ? 'bg-emerald-500/30 text-white shadow-lg'
                      : 'bg-emerald-500/20 text-emerald-700 shadow-md'
                    : theme === 'dark'
                      ? 'text-white/70 hover:bg-white/10 hover:text-white'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                )
              }
            >
              <item.icon className={cn(
                "w-5 h-5 group-hover:scale-110 transition-transform duration-300 ease-in-out",
                !sidebarCollapsed && "flex-shrink-0"
              )} />
              {!sidebarCollapsed && <span className="font-medium">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Theme Toggle & User section */}
        <div className={cn(
          "p-4 border-t",
          theme === 'dark' ? 'border-white/10' : 'border-slate-200'
        )}>
          {/* Theme Toggle */}
          <div className={cn(
            "mb-4 flex items-center gap-3 px-2",
            sidebarCollapsed && "justify-center"
          )}>
            <ThemeToggle />
            {!sidebarCollapsed && (
              <span className={cn(
                "text-sm",
                theme === 'dark' ? 'text-white/60' : 'text-slate-500'
              )}>
                {theme === 'dark' ? 'Modo Escuro' : 'Modo Claro'}
              </span>
            )}
          </div>

          <NavLink
            to={isSuperAdmin ? '/superadmin' : '/app/profile'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 mb-4 px-2 py-2 rounded-xl transition-all',
                'cursor-pointer group',
                theme === 'dark'
                  ? 'hover:bg-white/10'
                  : 'hover:bg-slate-100',
                isActive && (theme === 'dark' ? 'bg-white/10' : 'bg-slate-100')
              )
            }
          >
            <img
              src={user?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'}
              alt={user?.name}
              className="w-10 h-10 rounded-full border-2 border-emerald-500/50 group-hover:border-emerald-500 transition-colors"
            />
            {!sidebarCollapsed && (
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "font-medium truncate",
                  theme === 'dark' ? 'text-white' : 'text-slate-800'
                )}>{user?.name}</p>
                <p className={cn(
                  "text-sm truncate",
                  theme === 'dark' ? 'text-white/50' : 'text-slate-500'
                )}>{user?.email}</p>
              </div>
            )}
          </NavLink>
          <button
            onClick={handleLogout}
            className={cn(
              sidebarCollapsed
                ? 'mx-auto grid h-12 w-12 place-items-center rounded-xl'
                : 'flex items-center gap-3 w-full px-4 py-3 rounded-xl',
              'group text-red-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300/60',
              'transition-colors duration-300 ease-in-out',
              theme === 'dark' ? 'hover:bg-red-500/20' : 'hover:bg-red-50'
            )}
            aria-label="Sair"
            title={sidebarCollapsed ? 'Sair' : undefined}
          >
            <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform duration-300 ease-in-out" />
            {!sidebarCollapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
