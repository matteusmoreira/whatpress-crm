import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building2,
  MessageSquare,
  Plug,
  TrendingUp,
  CreditCard,
  Users,
  ArrowRight
} from 'lucide-react';
import { GlassCard } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';
import AnimatedCounter from '../components/AnimatedCounter';

const KPICard = ({ icon: Icon, label, value, trend, color }) => (
  <GlassCard className="p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-muted-foreground text-sm mb-1">{label}</p>
        <p className="text-3xl font-bold text-foreground">
          <AnimatedCounter value={value} duration={800} />
        </p>
        {trend && (
          <p className="text-emerald-400 text-sm mt-1 flex items-center gap-1">
            <TrendingUp className="w-4 h-4" /> {trend}
          </p>
        )}
      </div>
      <div className={cn('p-3 rounded-xl transition-transform hover:scale-110', color)}>
        <Icon className="w-6 h-6 text-white" />
      </div>
    </div>
  </GlassCard>
);

const QuickAccessCard = ({ to, icon: Icon, label, description, color }) => (
  <Link to={to}>
    <GlassCard className="p-5 group cursor-pointer">
      <div className="flex items-start gap-4">
        <div className={cn('p-3 rounded-xl transition-transform group-hover:scale-110', color)}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div className="flex-1">
          <h3 className="text-foreground font-semibold mb-1">{label}</h3>
          <p className="text-muted-foreground text-sm">{description}</p>
        </div>
        <ArrowRight className="w-5 h-5 text-muted-foreground/50 group-hover:text-foreground/70 group-hover:translate-x-1 transition-all" />
      </div>
    </GlassCard>
  </Link>
);

const SuperAdminDashboard = () => {
  const { stats, tenantsLoading, fetchTenants } = useAppStore();

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  return (
    <div className="min-h-screen p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">Dashboard SuperAdmin</h1>
        <p className="text-muted-foreground">Visão geral do sistema e acesso rápido às funcionalidades</p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <KPICard
          icon={Building2}
          label="Total de Tenants"
          value={stats?.totalTenants || 0}
          trend={`${stats?.activeTenants || 0} ativos`}
          color="bg-emerald-500/30"
        />
        <KPICard
          icon={MessageSquare}
          label="Mensagens / Dia"
          value={stats?.messagesPerDay || 0}
          color="bg-blue-500/30"
        />
        <KPICard
          icon={Plug}
          label="Conexões Ativas"
          value={stats?.totalConnections || 0}
          color="bg-purple-500/30"
        />
        <KPICard
          icon={TrendingUp}
          label="Mensagens / Mês"
          value={stats?.totalMessages || 0}
          color="bg-amber-500/30"
        />
      </div>

      {/* Quick Access */}
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-foreground mb-4">Acesso Rápido</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <QuickAccessCard
            to="/superadmin/tenants"
            icon={Building2}
            label="Gerenciar Tenants"
            description="Visualize, crie e edite tenants do sistema"
            color="bg-emerald-500/30"
          />
          <QuickAccessCard
            to="/superadmin/plans"
            icon={CreditCard}
            label="Gerenciar Planos"
            description="Configure planos e limites de recursos"
            color="bg-blue-500/30"
          />
          <QuickAccessCard
            to="/superadmin/users"
            icon={Users}
            label="Gerenciar Usuários"
            description="Crie usuários e atribua a tenants"
            color="bg-purple-500/30"
          />
        </div>
      </div>

      {/* Loading indicator */}
      {tenantsLoading && (
        <div className="flex items-center justify-center py-8">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}
    </div>
  );
};

export default SuperAdminDashboard;
