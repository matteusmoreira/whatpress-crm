import React, { useEffect, useMemo, useState } from 'react';
import {
  User,
  Bell,
  Shield,
  Globe,
  CreditCard,
  ChevronRight,
  Plug,
  Tag
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlassBadge, GlassCard } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';

const SettingItem = ({ icon: Icon, title, description, to, comingSoon }) => {
  const Component = to ? Link : 'div';
  const props = to ? { to } : {};

  return (
    <Component
      {...props}
      className={cn(
        'flex items-center gap-4 p-4 rounded-xl transition-all',
        to && 'hover:bg-white/10 cursor-pointer group',
        comingSoon && 'opacity-60 cursor-not-allowed'
      )}
    >
      <div className="p-3 rounded-xl bg-emerald-500/20 group-hover:bg-emerald-500/30 transition-colors">
        <Icon className="w-5 h-5 text-emerald-400" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-white font-medium">{title}</h3>
          {comingSoon && (
            <GlassBadge variant="warning" className="text-xs px-2 py-0.5">
              Em breve
            </GlassBadge>
          )}
        </div>
        <p className="text-white/50 text-sm">{description}</p>
      </div>
      {to && <ChevronRight className="w-5 h-5 text-white/30 group-hover:text-white/60 group-hover:translate-x-1 transition-all" />}
    </Component>
  );
};

const NOTIFICATION_PREFS_KEY = 'whatsapp-crm-notification-prefs-v1';

const loadNotificationPrefs = () => {
  if (typeof window === 'undefined') return { browserNotifications: false, sound: true };
  try {
    const raw = window.localStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (!raw) return { browserNotifications: false, sound: true };
    const parsed = JSON.parse(raw);
    return {
      browserNotifications: !!parsed?.browserNotifications,
      sound: parsed?.sound === false ? false : true
    };
  } catch (e) {
    return { browserNotifications: false, sound: true };
  }
};

const saveNotificationPrefs = (next) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(NOTIFICATION_PREFS_KEY, JSON.stringify(next));
  } catch (e) { }
};

const ToggleRow = ({ title, description, value, onToggle, disabled }) => {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
      <div className="pr-4">
        <p className="text-white font-medium">{title}</p>
        <p className="text-white/50 text-sm">{description}</p>
      </div>
      <button
        type="button"
        onClick={() => {
          if (disabled) return;
          onToggle?.();
        }}
        className={cn(
          'relative w-11 h-6 rounded-full transition-all duration-300',
          value ? 'bg-emerald-500' : 'bg-white/20',
          disabled && 'opacity-60 cursor-not-allowed'
        )}
        aria-pressed={!!value}
      >
        <span
          className={cn(
            'absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-all duration-300',
            value ? 'left-6' : 'left-1'
          )}
        />
      </button>
    </div>
  );
};

const Settings = () => {
  const { user } = useAuthStore();
  const { brandName, setBrandName } = useAppStore();
  const [brandNameInput, setBrandNameInput] = useState(brandName || 'WhatsApp CRM');

  const initialPrefs = useMemo(() => loadNotificationPrefs(), []);
  const [browserNotifications, setBrowserNotifications] = useState(initialPrefs.browserNotifications);
  const [sound, setSound] = useState(initialPrefs.sound);
  const [permission, setPermission] = useState(
    typeof window !== 'undefined' && 'Notification' in window ? window.Notification.permission : 'unsupported'
  );

  useEffect(() => {
    setBrandNameInput(brandName || 'WhatsApp CRM');
  }, [brandName]);

  useEffect(() => {
    saveNotificationPrefs({ browserNotifications, sound });
  }, [browserNotifications, sound]);

  useEffect(() => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      setPermission('unsupported');
      return;
    }
    setPermission(window.Notification.permission);
  }, []);

  const settingsSections = [
    {
      title: 'Conta',
      items: [
        {
          icon: User,
          title: 'Perfil',
          description: 'Gerencie suas informações pessoais',
          to: '/app/settings/profile'
        },
        {
          icon: Plug,
          title: 'Conexões WhatsApp',
          description: 'Configure seus provedores de mensagens',
          to: '/app/settings/connections'
        },
        {
          icon: Bell,
          title: 'Notificações',
          description: 'Configure alertas e notificações',
          comingSoon: false
        },
        {
          icon: Shield,
          title: 'Segurança',
          description: 'Senha e autenticação de dois fatores',
          comingSoon: true
        }
      ]
    },
    {
      title: 'Preferências',
      items: [
        {
          icon: Globe,
          title: 'Idioma e Região',
          description: 'Idioma, fuso horário e formato de data',
          comingSoon: true
        }
      ]
    },
    {
      title: 'Assinatura',
      items: [
        {
          icon: CreditCard,
          title: 'Plano e Faturamento',
          description: 'Gerencie sua assinatura e pagamentos',
          comingSoon: true
        }
      ]
    }
  ];

  return (
    <div className="min-h-screen p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Configurações</h1>
        <p className="text-white/60">Gerencie suas preferências e configurações da conta</p>
      </div>

      {/* User Card */}
      <GlassCard className="mb-8 p-6">
        <div className="flex items-center gap-4">
          <img
            src={user?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'}
            alt={user?.name}
            className="w-16 h-16 rounded-full border-2 border-emerald-500/50"
          />
          <div>
            <h2 className="text-xl font-bold text-white">{user?.name}</h2>
            <p className="text-white/60">{user?.email}</p>
            <GlassBadge variant="success" className="inline-block mt-2 px-3 py-1 text-sm font-medium capitalize">
              {user?.role}
            </GlassBadge>
          </div>
        </div>
      </GlassCard>

      <GlassCard className="mb-8 p-6" hover={false}>
        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 rounded-xl bg-emerald-500/20">
            <Tag className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">White-label</h2>
            <p className="text-white/60 text-sm">Altere o nome exibido no topo do menu</p>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-white/80 text-sm font-medium block mb-2">Nome do sistema</label>
            <input
              type="text"
              value={brandNameInput}
              onChange={(e) => setBrandNameInput(e.target.value)}
              placeholder="WhatsApp CRM"
              className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => {
                setBrandName(brandNameInput);
                toast.success('Nome atualizado');
              }}
              className="px-4 py-2 rounded-xl bg-emerald-500 text-white font-medium hover:bg-emerald-600 transition-colors"
            >
              Aplicar
            </button>
          </div>
        </div>
      </GlassCard>

      <GlassCard className="mb-8 p-6" hover={false}>
        <div className="flex items-center gap-3 mb-4">
          <div className="p-3 rounded-xl bg-emerald-500/20">
            <Bell className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Notificações</h2>
            <p className="text-white/60 text-sm">
              {permission === 'granted'
                ? 'Permissão do navegador: concedida'
                : permission === 'denied'
                  ? 'Permissão do navegador: bloqueada'
                  : permission === 'default'
                    ? 'Permissão do navegador: não configurada'
                    : 'Permissão do navegador: indisponível'}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          <ToggleRow
            title="Notificação no navegador"
            description="Mostra um alerta quando chegar mensagem nova"
            value={browserNotifications}
            disabled={permission === 'unsupported'}
            onToggle={async () => {
              const next = !browserNotifications;
              if (!next) {
                setBrowserNotifications(false);
                return;
              }

              if (typeof window === 'undefined' || !('Notification' in window)) {
                setPermission('unsupported');
                setBrowserNotifications(false);
                toast.warning('Seu navegador não suporta notificações');
                return;
              }

              const currentPermission = window.Notification.permission;
              setPermission(currentPermission);
              if (currentPermission === 'granted') {
                setBrowserNotifications(true);
                return;
              }
              if (currentPermission === 'denied') {
                setBrowserNotifications(false);
                toast.warning('Notificações bloqueadas no navegador');
                return;
              }

              try {
                const result = await window.Notification.requestPermission();
                setPermission(result);
                if (result === 'granted') {
                  setBrowserNotifications(true);
                } else {
                  setBrowserNotifications(false);
                  toast.info('Notificações não foram ativadas');
                }
              } catch (e) {
                setBrowserNotifications(false);
                toast.error('Não foi possível pedir permissão de notificação');
              }
            }}
          />

          <ToggleRow
            title="Aviso sonoro"
            description="Toca um som simples quando chegar mensagem nova"
            value={sound}
            onToggle={() => setSound(s => !s)}
          />
        </div>
      </GlassCard>

      {/* Settings Sections */}
      <div className="space-y-6">
        {settingsSections.map((section) => (
          <GlassCard key={section.title} hover={false}>
            <h3 className="text-lg font-semibold text-white px-4 pt-4 pb-2">{section.title}</h3>
            <div className="divide-y divide-white/5">
              {section.items.map((item) => (
                <SettingItem key={item.title} {...item} />
              ))}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};

export default Settings;
