import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  Settings,
  Users,
  LogOut,
  Menu,
  X,
  Building2,
  Plug,
  Search,
  User
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useAppStore } from '../../store/appStore';
import { cn } from '../../lib/utils';
import SearchModal from '../SearchModal';
import { toast } from '../ui/glass-toaster';

const Sidebar = () => {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar, conversations } = useAppStore();
  const navigate = useNavigate();
  const [showSearch, setShowSearch] = useState(false);

  const handleLogout = () => {
    logout();
    toast.success('Até logo!', { description: 'Você foi desconectado com sucesso.' });
    navigate('/sign-in');
  };

  const isSuperAdmin = user?.role === 'superadmin';

  const navItems = isSuperAdmin
    ? [
        { to: '/superadmin', icon: LayoutDashboard, label: 'Dashboard' },
        { to: '/superadmin/tenants', icon: Building2, label: 'Tenants' },
      ]
    : [
        { to: '/app/inbox', icon: MessageSquare, label: 'Inbox' },
        { to: '/app/settings/connections', icon: Plug, label: 'Conexões' },
        { to: '/app/settings', icon: Settings, label: 'Configurações' },
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
        onClick={toggleSidebar}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-emerald-600 text-white shadow-lg"
      >
        {sidebarCollapsed ? <Menu size={24} /> : <X size={24} />}
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
          'w-72 min-h-screen',
          'backdrop-blur-xl bg-gradient-to-b from-emerald-900/90 to-emerald-950/95',
          'border-r border-white/10',
          'flex flex-col',
          'transition-transform duration-300 ease-in-out',
          sidebarCollapsed ? '-translate-x-full lg:translate-x-0 lg:w-20' : 'translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="p-6 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-xl font-bold text-white">WhatsApp CRM</span>
            )}
          </div>
        </div>

        {/* Search Button */}
        {!isSuperAdmin && (
          <div className="p-4 border-b border-white/10">
            <button
              onClick={() => setShowSearch(true)}
              className={cn(
                'flex items-center gap-3 w-full px-4 py-3 rounded-xl',
                'bg-white/5 hover:bg-white/10 text-white/70 hover:text-white',
                'transition-all duration-200 group'
              )}
            >
              <Search className="w-5 h-5 flex-shrink-0 group-hover:scale-110 transition-transform" />
              {!sidebarCollapsed && (
                <>
                  <span className="flex-1 text-left text-sm">Buscar...</span>
                  <kbd className="hidden lg:inline px-1.5 py-0.5 rounded bg-white/10 text-xs">\u2318K</kbd>
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
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-4 py-3 rounded-xl',
                  'transition-all duration-200 group',
                  isActive
                    ? 'bg-emerald-500/30 text-white shadow-lg'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                )
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0 group-hover:scale-110 transition-transform" />
              {!sidebarCollapsed && <span className="font-medium">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-white/10">
          <NavLink
            to={isSuperAdmin ? '/superadmin' : '/app/profile'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 mb-4 px-2 py-2 rounded-xl transition-all',
                'hover:bg-white/10 cursor-pointer group',
                isActive && 'bg-white/10'
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
                <p className="text-white font-medium truncate">{user?.name}</p>
                <p className="text-white/50 text-sm truncate">{user?.email}</p>
              </div>
            )}
          </NavLink>
          <button
            onClick={handleLogout}
            className={cn(
              'flex items-center gap-3 w-full px-4 py-3 rounded-xl',
              'text-red-400 hover:bg-red-500/20 transition-all duration-200 group'
            )}
          >
            <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
            {!sidebarCollapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
