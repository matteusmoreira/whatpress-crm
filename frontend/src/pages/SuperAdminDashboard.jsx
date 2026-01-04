import React, { useEffect, useState } from 'react';
import {
  Building2,
  MessageSquare,
  Plug,
  TrendingUp,
  Plus,
  Search,
  MoreVertical,
  Edit,
  Trash2,
  X
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';
import AnimatedCounter from '../components/AnimatedCounter';

const KPICard = ({ icon: Icon, label, value, trend, color }) => (
  <GlassCard className="p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-white/60 text-sm mb-1">{label}</p>
        <p className="text-3xl font-bold text-white">
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

const SuperAdminDashboard = () => {
  const { tenants, stats, tenantsLoading, fetchTenants, createTenant, deleteTenant } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSlug, setNewTenantSlug] = useState('');

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  const filteredTenants = tenants.filter(tenant => {
    const matchesSearch = tenant.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || tenant.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleCreateTenant = async (e) => {
    e.preventDefault();
    await createTenant({
      name: newTenantName,
      slug: newTenantSlug || newTenantName.toLowerCase().replace(/\s+/g, '-')
    });
    setShowCreateModal(false);
    setNewTenantName('');
    setNewTenantSlug('');
    fetchTenants();
    toast.success('Tenant criado!', { description: `${newTenantName} foi adicionado com sucesso.` });
  };

  const handleDeleteTenant = async (id, name) => {
    if (window.confirm('Tem certeza que deseja excluir este tenant?')) {
      await deleteTenant(id);
      fetchTenants();
      toast.success('Tenant removido', { description: `${name} foi excluído.` });
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      active: { variant: 'success', label: 'Ativo' },
      inactive: { variant: 'warning', label: 'Inativo' },
      suspended: { variant: 'danger', label: 'Suspenso' }
    };
    const { variant, label } = variants[status] || variants.inactive;
    return <GlassBadge variant={variant}>{label}</GlassBadge>;
  };

  const getPlanBadge = (plan) => {
    const colors = {
      free: 'bg-gray-500/30 text-gray-300',
      starter: 'bg-blue-500/30 text-blue-300',
      pro: 'bg-purple-500/30 text-purple-300',
      enterprise: 'bg-amber-500/30 text-amber-300'
    };
    return (
      <span className={cn('px-2 py-1 rounded-lg text-xs font-medium uppercase', colors[plan])}>
        {plan}
      </span>
    );
  };

  return (
    <div className="min-h-screen p-6 lg:p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard SuperAdmin</h1>
        <p className="text-white/60">Gerencie todos os tenants e monitore o sistema</p>
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
          value={stats?.totalMessages?.toLocaleString() || 0}
          color="bg-amber-500/30"
        />
      </div>

      {/* Filters and Actions */}
      <div className="flex flex-col lg:flex-row gap-4 mb-6">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
          <GlassInput
            type="text"
            placeholder="Pesquisar tenants..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-12"
          />
        </div>
        <div className="flex gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todos</option>
            <option value="active" className="bg-emerald-900">Ativos</option>
            <option value="inactive" className="bg-emerald-900">Inativos</option>
            <option value="suspended" className="bg-emerald-900">Suspensos</option>
          </select>
          <GlassButton onClick={() => setShowCreateModal(true)} className="flex items-center gap-2">
            <Plus className="w-5 h-5" />
            <span className="hidden sm:inline">Criar Tenant</span>
          </GlassButton>
        </div>
      </div>

      {/* Tenants Table */}
      <GlassCard className="overflow-hidden" hover={false}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-4 text-white/60 font-medium">Tenant</th>
                <th className="text-left p-4 text-white/60 font-medium">Plano</th>
                <th className="text-left p-4 text-white/60 font-medium">Status</th>
                <th className="text-left p-4 text-white/60 font-medium">Msgs/Mês</th>
                <th className="text-left p-4 text-white/60 font-medium">Conexões</th>
                <th className="text-right p-4 text-white/60 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {tenantsLoading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-white/60">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                      Carregando...
                    </div>
                  </td>
                </tr>
              ) : filteredTenants.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-white/60">
                    Nenhum tenant encontrado
                  </td>
                </tr>
              ) : (
                filteredTenants.map((tenant) => (
                  <tr
                    key={tenant.id}
                    className="border-b border-white/5 hover:bg-white/5 transition-colors"
                  >
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-emerald-500/30 flex items-center justify-center">
                          <Building2 className="w-5 h-5 text-emerald-400" />
                        </div>
                        <div>
                          <p className="text-white font-medium">{tenant.name}</p>
                          <p className="text-white/50 text-sm">/{tenant.slug}</p>
                        </div>
                      </div>
                    </td>
                    <td className="p-4">{getPlanBadge(tenant.plan)}</td>
                    <td className="p-4">{getStatusBadge(tenant.status)}</td>
                    <td className="p-4 text-white">{tenant.messagesThisMonth.toLocaleString()}</td>
                    <td className="p-4 text-white">{tenant.connectionsCount}</td>
                    <td className="p-4">
                      <div className="flex items-center justify-end gap-2">
                        <button className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors">
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteTenant(tenant.id)}
                          className="p-2 rounded-lg hover:bg-red-500/20 text-white/60 hover:text-red-400 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>

      {/* Create Tenant Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <GlassCard className="w-full max-w-md" hover={false}>
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white">Criar Novo Tenant</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateTenant} className="space-y-4">
              <div>
                <label className="text-white/80 text-sm font-medium block mb-2">Nome da Empresa</label>
                <GlassInput
                  type="text"
                  placeholder="Ex: Minha Empresa"
                  value={newTenantName}
                  onChange={(e) => setNewTenantName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="text-white/80 text-sm font-medium block mb-2">Slug (URL)</label>
                <GlassInput
                  type="text"
                  placeholder="Ex: minha-empresa"
                  value={newTenantSlug}
                  onChange={(e) => setNewTenantSlug(e.target.value)}
                />
              </div>
              <div className="flex gap-3 pt-4">
                <GlassButton
                  type="button"
                  variant="secondary"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1"
                >
                  Cancelar
                </GlassButton>
                <GlassButton type="submit" className="flex-1">
                  Criar Tenant
                </GlassButton>
              </div>
            </form>
          </GlassCard>
        </div>
      )}
    </div>
  );
};

export default SuperAdminDashboard;
