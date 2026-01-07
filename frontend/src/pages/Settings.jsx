import React from 'react';
import {
  User,
  Bell,
  Shield,
  Globe,
  CreditCard,
  ChevronRight,
  Plug
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlassBadge, GlassCard } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { cn } from '../lib/utils';

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

const Settings = () => {
  const { user } = useAuthStore();

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
          comingSoon: true
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
