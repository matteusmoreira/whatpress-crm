import React, { useState } from 'react';
import {
  User,
  Mail,
  Phone,
  Building2,
  Shield,
  Camera,
  Save,
  Bell,
  Moon,
  Sun,
  Globe,
  Key
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useTheme } from '../context/ThemeContext';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const Profile = () => {
  const { user } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: '+55 21 99999-8888',
    company: 'Minha Empresa',
    bio: 'Gerente de atendimento ao cliente com foco em experiência do usuário.'
  });

  const [notifications, setNotifications] = useState({
    newMessages: true,
    mentions: true,
    updates: false,
    marketing: false
  });

  const handleSave = () => {
    setIsEditing(false);
    toast.success('Perfil atualizado com sucesso!', {
      description: 'Suas alterações foram salvas.'
    });
  };

  const handleAvatarChange = () => {
    toast.info('Funcionalidade em breve', {
      description: 'Upload de avatar será implementado na próxima versão.'
    });
  };

  const handlePasswordChange = () => {
    toast.info('Email enviado', {
      description: 'Verifique seu email para redefinir a senha.'
    });
  };

  return (
    <div className="min-h-screen p-6 lg:p-8 overflow-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Meu Perfil</h1>
        <p className="text-white/60">Gerencie suas informações pessoais e preferências</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Card */}
        <GlassCard className="lg:col-span-1 p-6" hover={false}>
          <div className="text-center">
            {/* Avatar */}
            <div className="relative inline-block mb-4">
              <img
                src={user?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'}
                alt={user?.name}
                className="w-28 h-28 rounded-full border-4 border-emerald-500/50 shadow-lg shadow-emerald-500/20"
              />
              <button
                onClick={handleAvatarChange}
                className="absolute bottom-0 right-0 p-2 rounded-full bg-emerald-500 text-white shadow-lg hover:bg-emerald-600 transition-all hover:scale-110 active:scale-95"
              >
                <Camera className="w-4 h-4" />
              </button>
            </div>

            <h2 className="text-xl font-bold text-white mb-1">{user?.name}</h2>
            <p className="text-white/60 mb-2">{user?.email}</p>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-sm font-medium capitalize">
              <Shield className="w-3.5 h-3.5" />
              {user?.role}
            </span>

            <div className="mt-6 pt-6 border-t border-white/10">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-white">1,247</p>
                  <p className="text-white/50 text-sm">Mensagens</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-white">89</p>
                  <p className="text-white/50 text-sm">Conversas</p>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* Info Card */}
        <GlassCard className="lg:col-span-2 p-6" hover={false}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white">Informações Pessoais</h3>
            {isEditing ? (
              <GlassButton onClick={handleSave} className="flex items-center gap-2">
                <Save className="w-4 h-4" />
                Salvar
              </GlassButton>
            ) : (
              <GlassButton variant="secondary" onClick={() => setIsEditing(true)}>
                Editar
              </GlassButton>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-white/70 text-sm font-medium flex items-center gap-2">
                <User className="w-4 h-4" /> Nome Completo
              </label>
              {isEditing ? (
                <GlassInput
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              ) : (
                <p className="text-white py-3">{formData.name}</p>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-white/70 text-sm font-medium flex items-center gap-2">
                <Mail className="w-4 h-4" /> Email
              </label>
              {isEditing ? (
                <GlassInput
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                />
              ) : (
                <p className="text-white py-3">{formData.email}</p>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-white/70 text-sm font-medium flex items-center gap-2">
                <Phone className="w-4 h-4" /> Telefone
              </label>
              {isEditing ? (
                <GlassInput
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                />
              ) : (
                <p className="text-white py-3">{formData.phone}</p>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-white/70 text-sm font-medium flex items-center gap-2">
                <Building2 className="w-4 h-4" /> Empresa
              </label>
              {isEditing ? (
                <GlassInput
                  value={formData.company}
                  onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                />
              ) : (
                <p className="text-white py-3">{formData.company}</p>
              )}
            </div>

            <div className="space-y-2 md:col-span-2">
              <label className="text-white/70 text-sm font-medium">Bio</label>
              {isEditing ? (
                <textarea
                  value={formData.bio}
                  onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                  rows={3}
                  className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                />
              ) : (
                <p className="text-white/80 py-3">{formData.bio}</p>
              )}
            </div>
          </div>
        </GlassCard>

        {/* Preferences Card */}
        <GlassCard className="lg:col-span-2 p-6" hover={false}>
          <h3 className="text-lg font-semibold text-white mb-6">Preferências</h3>
          
          <div className="space-y-6">
            {/* Theme Toggle */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <div className="flex items-center gap-3">
                {theme === 'dark' ? (
                  <Moon className="w-5 h-5 text-emerald-400" />
                ) : (
                  <Sun className="w-5 h-5 text-amber-400" />
                )}
                <div>
                  <p className="text-white font-medium">Tema</p>
                  <p className="text-white/50 text-sm">{theme === 'dark' ? 'Modo Escuro' : 'Modo Claro'}</p>
                </div>
              </div>
              <button
                onClick={toggleTheme}
                className={cn(
                  'relative w-14 h-8 rounded-full transition-all duration-300',
                  theme === 'dark' ? 'bg-emerald-500' : 'bg-white/30'
                )}
              >
                <span
                  className={cn(
                    'absolute top-1 w-6 h-6 rounded-full bg-white shadow-lg transition-all duration-300',
                    theme === 'dark' ? 'left-7' : 'left-1'
                  )}
                />
              </button>
            </div>

            {/* Language */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <div className="flex items-center gap-3">
                <Globe className="w-5 h-5 text-blue-400" />
                <div>
                  <p className="text-white font-medium">Idioma</p>
                  <p className="text-white/50 text-sm">Português (Brasil)</p>
                </div>
              </div>
              <select className="px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none">
                <option value="pt-BR" className="bg-emerald-900">Português (BR)</option>
                <option value="en" className="bg-emerald-900">English</option>
                <option value="es" className="bg-emerald-900">Español</option>
              </select>
            </div>

            {/* Change Password */}
            <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <div className="flex items-center gap-3">
                <Key className="w-5 h-5 text-amber-400" />
                <div>
                  <p className="text-white font-medium">Senha</p>
                  <p className="text-white/50 text-sm">Última alteração há 30 dias</p>
                </div>
              </div>
              <GlassButton variant="secondary" onClick={handlePasswordChange} className="text-sm">
                Alterar Senha
              </GlassButton>
            </div>
          </div>
        </GlassCard>

        {/* Notifications Card */}
        <GlassCard className="lg:col-span-1 p-6" hover={false}>
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <Bell className="w-5 h-5" /> Notificações
          </h3>
          
          <div className="space-y-4">
            {[
              { key: 'newMessages', label: 'Novas mensagens', desc: 'Receber alerta de novas mensagens' },
              { key: 'mentions', label: 'Menções', desc: 'Quando alguém te mencionar' },
              { key: 'updates', label: 'Atualizações', desc: 'Novidades do sistema' },
              { key: 'marketing', label: 'Marketing', desc: 'Promoções e novidades' }
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between">
                <div>
                  <p className="text-white font-medium text-sm">{item.label}</p>
                  <p className="text-white/50 text-xs">{item.desc}</p>
                </div>
                <button
                  onClick={() => {
                    setNotifications(prev => ({ ...prev, [item.key]: !prev[item.key] }));
                    toast.success(notifications[item.key] ? 'Notificação desativada' : 'Notificação ativada');
                  }}
                  className={cn(
                    'relative w-11 h-6 rounded-full transition-all duration-300',
                    notifications[item.key] ? 'bg-emerald-500' : 'bg-white/20'
                  )}
                >
                  <span
                    className={cn(
                      'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-300',
                      notifications[item.key] ? 'left-6' : 'left-1'
                    )}
                  />
                </button>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

export default Profile;
