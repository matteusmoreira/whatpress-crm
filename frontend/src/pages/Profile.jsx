import React, { useState, useEffect, useRef } from 'react';
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
  Key,
  Loader2
} from 'lucide-react';
import { GlassBadge, GlassCard, GlassInput, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useTheme } from '../context/ThemeContext';
import { TenantsAPI, UploadAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const Profile = () => {
  const { user, updateCurrentUser } = useAuthStore();
  const { theme, toggleTheme } = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isAvatarUploading, setIsAvatarUploading] = useState(false);
  const avatarInputRef = useRef(null);
  const [initialCompany, setInitialCompany] = useState('');
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    company: '',
    bio: user?.bio || '',
    jobTitle: user?.jobTitle || '',
    department: user?.department || '',
    signatureEnabled: user?.signatureEnabled ?? true,
    signatureIncludeTitle: user?.signatureIncludeTitle ?? false,
    signatureIncludeDepartment: user?.signatureIncludeDepartment ?? false
  });

  const [notifications, setNotifications] = useState({
    newMessages: true,
    mentions: true,
    updates: false,
    marketing: false
  });

  // Buscar dados do tenant
  useEffect(() => {
    const loadTenant = async () => {
      if (user?.tenantId) {
        try {
          const tenant = await TenantsAPI.getById(user.tenantId);
          const nextCompany = tenant.name || tenant.companyName || '';
          setFormData(prev => ({ ...prev, company: nextCompany }));
          setInitialCompany(nextCompany);
        } catch (error) {
          console.error('Error loading tenant:', error);
        }
      }
    };
    loadTenant();
  }, [user?.tenantId]);

  useEffect(() => {
    setFormData(prev => ({
      ...prev,
      name: user?.name || '',
      email: user?.email || '',
      phone: user?.phone || '',
      bio: user?.bio || '',
      jobTitle: user?.jobTitle || '',
      department: user?.department || '',
      signatureEnabled: user?.signatureEnabled ?? true,
      signatureIncludeTitle: user?.signatureIncludeTitle ?? false,
      signatureIncludeDepartment: user?.signatureIncludeDepartment ?? false
    }));
  }, [user]);

  const handleSave = async () => {
    const name = (formData.name || '').trim();
    if (!name) {
      toast.error('Nome é obrigatório');
      return;
    }

    setIsSaving(true);
    try {
      const updatedUser = await updateCurrentUser({
        name,
        email: (formData.email || '').trim(),
        phone: (formData.phone || '').trim(),
        bio: (formData.bio || '').trim(),
        jobTitle: formData.jobTitle || '',
        department: formData.department || '',
        signatureEnabled: Boolean(formData.signatureEnabled),
        signatureIncludeTitle: Boolean(formData.signatureIncludeTitle),
        signatureIncludeDepartment: Boolean(formData.signatureIncludeDepartment)
      });

      if (user?.role === 'admin' && user?.tenantId) {
        const nextCompany = (formData.company || '').trim();
        if (nextCompany && nextCompany !== (initialCompany || '').trim()) {
          try {
            await TenantsAPI.update(user.tenantId, { name: nextCompany });
            setInitialCompany(nextCompany);
          } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar empresa');
          }
        }
      }

      setFormData(prev => ({
        ...prev,
        name: updatedUser?.name || prev.name,
        email: updatedUser?.email || prev.email,
        phone: updatedUser?.phone || '',
        bio: updatedUser?.bio || '',
        jobTitle: updatedUser?.jobTitle || '',
        department: updatedUser?.department || '',
        signatureEnabled: updatedUser?.signatureEnabled ?? true,
        signatureIncludeTitle: updatedUser?.signatureIncludeTitle ?? false,
        signatureIncludeDepartment: updatedUser?.signatureIncludeDepartment ?? false
      }));

      setIsEditing(false);
      toast.success('Perfil atualizado com sucesso!', {
        description: 'Suas alterações foram salvas.'
      });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erro ao salvar perfil');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAvatarChange = () => {
    if (isAvatarUploading) return;
    avatarInputRef.current?.click();
  };

  const handleAvatarFileSelected = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (!String(file.type || '').startsWith('image/')) {
      toast.error('Selecione uma imagem válida');
      return;
    }

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('Arquivo muito grande', { description: 'Máximo permitido: 10MB' });
      return;
    }

    setIsAvatarUploading(true);
    try {
      const uploadResult = await UploadAPI.uploadFile(file, user?.id || 'avatar');
      await updateCurrentUser({ avatar: uploadResult.url });
      toast.success('Avatar atualizado com sucesso!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Erro ao atualizar avatar');
    } finally {
      setIsAvatarUploading(false);
    }
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
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/*"
                onChange={handleAvatarFileSelected}
                className="hidden"
              />
              <img
                src={user?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'}
                alt={user?.name}
                className="w-28 h-28 rounded-full border-4 border-emerald-500/50 shadow-lg shadow-emerald-500/20"
              />
              <button
                onClick={handleAvatarChange}
                disabled={isAvatarUploading}
                className="absolute bottom-0 right-0 p-2 rounded-full bg-emerald-500 text-white shadow-lg hover:bg-emerald-600 transition-all hover:scale-110 active:scale-95"
              >
                {isAvatarUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Camera className="w-4 h-4" />}
              </button>
            </div>

            <h2 className="text-xl font-bold text-white mb-1">{user?.name}</h2>
            <p className="text-white/60 mb-2">{user?.email}</p>
            <GlassBadge variant="success" className="inline-flex items-center gap-1.5 text-sm font-medium capitalize">
              <Shield className="w-3.5 h-3.5" />
              {user?.role}
            </GlassBadge>

            <div className="mt-6 pt-6 border-t border-white/10">
              <p className="text-white/50 text-sm text-center">
                Membro desde {new Date(user?.createdAt || Date.now()).toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}
              </p>
            </div>
          </div>
        </GlassCard>

        {/* Info Card */}
        <GlassCard className="lg:col-span-2 p-6" hover={false}>
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white">Informações Pessoais</h3>
            {isEditing ? (
              <GlassButton onClick={handleSave} className="flex items-center gap-2" disabled={isSaving}>
                {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {isSaving ? 'Salvando...' : 'Salvar'}
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
                  disabled={isSaving}
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
                  disabled={isSaving}
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
                  disabled={isSaving || user?.role !== 'admin'}
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
                  disabled={isSaving}
                  rows={3}
                  className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                />
              ) : (
                <p className="text-white/80 py-3">{formData.bio}</p>
              )}
            </div>

            <div className="space-y-4 md:col-span-2 pt-6 border-t border-white/10">
              <h4 className="text-white font-semibold">Assinatura</h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-white/70 text-sm font-medium">Cargo</label>
                  {isEditing ? (
                    <GlassInput
                      value={formData.jobTitle}
                      onChange={(e) => setFormData({ ...formData, jobTitle: e.target.value })}
                      disabled={isSaving}
                    />
                  ) : (
                    <p className="text-white/80 py-3">{formData.jobTitle || '—'}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-white/70 text-sm font-medium">Departamento</label>
                  {isEditing ? (
                    <GlassInput
                      value={formData.department}
                      onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                      disabled={isSaving}
                    />
                  ) : (
                    <p className="text-white/80 py-3">{formData.department || '—'}</p>
                  )}
                </div>

                <div className="md:col-span-2 flex items-center justify-between p-4 rounded-xl bg-white/5">
                  <div>
                    <p className="text-white font-medium">Ativar assinatura</p>
                    <p className="text-white/50 text-sm">Inclui seu nome no início das mensagens</p>
                  </div>
                  <button
                    onClick={() => {
                      if (!isEditing || isSaving) return;
                      setFormData(prev => ({ ...prev, signatureEnabled: !prev.signatureEnabled }));
                    }}
                    className={cn(
                      'relative w-11 h-6 rounded-full transition-all duration-300',
                      formData.signatureEnabled ? 'bg-emerald-500' : 'bg-white/20',
                      (!isEditing || isSaving) && 'opacity-60 cursor-not-allowed'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-300',
                        formData.signatureEnabled ? 'left-6' : 'left-1'
                      )}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                  <div>
                    <p className="text-white font-medium">Incluir cargo</p>
                    <p className="text-white/50 text-sm">Exibe o cargo junto ao seu nome</p>
                  </div>
                  <button
                    onClick={() => {
                      if (!isEditing || isSaving || !formData.signatureEnabled) return;
                      setFormData(prev => ({ ...prev, signatureIncludeTitle: !prev.signatureIncludeTitle }));
                    }}
                    className={cn(
                      'relative w-11 h-6 rounded-full transition-all duration-300',
                      formData.signatureEnabled && formData.signatureIncludeTitle ? 'bg-emerald-500' : 'bg-white/20',
                      (!isEditing || isSaving || !formData.signatureEnabled) && 'opacity-60 cursor-not-allowed'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-300',
                        formData.signatureEnabled && formData.signatureIncludeTitle ? 'left-6' : 'left-1'
                      )}
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                  <div>
                    <p className="text-white font-medium">Incluir departamento</p>
                    <p className="text-white/50 text-sm">Exibe o departamento junto ao seu nome</p>
                  </div>
                  <button
                    onClick={() => {
                      if (!isEditing || isSaving || !formData.signatureEnabled) return;
                      setFormData(prev => ({ ...prev, signatureIncludeDepartment: !prev.signatureIncludeDepartment }));
                    }}
                    className={cn(
                      'relative w-11 h-6 rounded-full transition-all duration-300',
                      formData.signatureEnabled && formData.signatureIncludeDepartment ? 'bg-emerald-500' : 'bg-white/20',
                      (!isEditing || isSaving || !formData.signatureEnabled) && 'opacity-60 cursor-not-allowed'
                    )}
                  >
                    <span
                      className={cn(
                        'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-300',
                        formData.signatureEnabled && formData.signatureIncludeDepartment ? 'left-6' : 'left-1'
                      )}
                    />
                  </button>
                </div>

                {/* Preview da Assinatura */}
                {formData.signatureEnabled && (
                  <div className="md:col-span-2 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                    <p className="text-white/70 text-sm mb-2">📝 Preview da assinatura nas mensagens:</p>
                    <div className="p-3 rounded-lg bg-black/20">
                      <p className="text-white">
                        <strong>*{formData.name || 'Seu Nome'}*</strong>
                        {((formData.signatureIncludeTitle && formData.jobTitle) ||
                          (formData.signatureIncludeDepartment && formData.department)) && (
                            <span className="text-white/70">
                              {' '}({[
                                formData.signatureIncludeTitle && formData.jobTitle,
                                formData.signatureIncludeDepartment && formData.department
                              ].filter(Boolean).join(' / ')})
                            </span>
                          )}
                      </p>
                      <p className="text-white/50 text-sm mt-1 italic">Sua mensagem aqui...</p>
                    </div>
                  </div>
                )}
              </div>
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
                  theme === 'dark' ? 'bg-emerald-500' : 'bg-slate-200 border border-slate-300'
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
