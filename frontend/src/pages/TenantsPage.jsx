import React, { useEffect, useState } from 'react';
import {
    Building2,
    Plus,
    Search,
    Edit,
    Trash2,
    X,
    TrendingUp,
    MessageSquare,
    Plug
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';
import { TenantsAPI, PlansAPI } from '../lib/api';

const TenantsPage = () => {
    const [tenants, setTenants] = useState([]);
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('all');
    const [showModal, setShowModal] = useState(false);
    const [editingTenant, setEditingTenant] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        slug: '',
        status: 'active',
        plan_id: ''
    });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [tenantsData, plansData] = await Promise.all([
                TenantsAPI.list(),
                PlansAPI.list()
            ]);
            setTenants(tenantsData);
            setPlans(plansData);
        } catch (error) {
            console.error('Error fetching data:', error);
            toast.error('Erro ao carregar dados');
        } finally {
            setLoading(false);
        }
    };

    const filteredTenants = tenants.filter(tenant => {
        const matchesSearch = tenant.name.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStatus = statusFilter === 'all' || tenant.status === statusFilter;
        return matchesSearch && matchesStatus;
    });

    const handleOpenModal = (tenant = null) => {
        if (tenant) {
            setEditingTenant(tenant);
            setFormData({
                name: tenant.name,
                slug: tenant.slug,
                status: tenant.status,
                plan_id: tenant.planId || ''
            });
        } else {
            setEditingTenant(null);
            setFormData({
                name: '',
                slug: '',
                status: 'active',
                plan_id: plans.length > 0 ? plans[0].id : ''
            });
        }
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setEditingTenant(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const data = { ...formData };
            if (!data.plan_id) {
                data.plan_id = null;
            }

            if (editingTenant) {
                await TenantsAPI.update(editingTenant.id, data);
                toast.success('Tenant atualizado!');
            } else {
                await TenantsAPI.create(data);
                toast.success('Tenant criado!');
            }
            handleCloseModal();
            fetchData();
        } catch (error) {
            console.error('Error saving tenant:', error);
            toast.error(error.response?.data?.detail || 'Erro ao salvar tenant');
        }
    };

    const handleDelete = async (id, name) => {
        if (window.confirm(`Tem certeza que deseja excluir o tenant "${name}"? Todos os dados serão perdidos.`)) {
            try {
                await TenantsAPI.delete(id);
                toast.success('Tenant excluído!');
                fetchData();
            } catch (error) {
                console.error('Error deleting tenant:', error);
                toast.error(error.response?.data?.detail || 'Erro ao excluir tenant');
            }
        }
    };

    const handleSlugGeneration = (name) => {
        const slug = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
        setFormData(prev => ({ ...prev, name, slug }));
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
            <span className={cn('px-2 py-1 rounded-lg text-xs font-medium uppercase', colors[plan] || colors.free)}>
                {plan || 'free'}
            </span>
        );
    };

    return (
        <div className="min-h-screen p-6 lg:p-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Gerenciar Tenants</h1>
                <p className="text-white/60">Visualize e gerencie todos os tenants do sistema</p>
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
                    <GlassButton onClick={() => handleOpenModal()} className="flex items-center gap-2">
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
                            {loading ? (
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
                                        <td className="p-4 text-white">{tenant.messagesThisMonth?.toLocaleString() || 0}</td>
                                        <td className="p-4 text-white">{tenant.connectionsCount || 0}</td>
                                        <td className="p-4">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => handleOpenModal(tenant)}
                                                    className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                >
                                                    <Edit className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(tenant.id, tenant.name)}
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

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <GlassCard className="w-full max-w-md" hover={false}>
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white">
                                {editingTenant ? 'Editar Tenant' : 'Criar Novo Tenant'}
                            </h2>
                            <button
                                onClick={handleCloseModal}
                                className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Nome da Empresa</label>
                                <GlassInput
                                    type="text"
                                    placeholder="Ex: Minha Empresa"
                                    value={formData.name}
                                    onChange={(e) => handleSlugGeneration(e.target.value)}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Slug (URL)</label>
                                <GlassInput
                                    type="text"
                                    placeholder="Ex: minha-empresa"
                                    value={formData.slug}
                                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Plano</label>
                                <select
                                    value={formData.plan_id}
                                    onChange={(e) => setFormData({ ...formData, plan_id: e.target.value })}
                                    className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                >
                                    <option value="" className="bg-emerald-900">Selecione um plano</option>
                                    {plans.map(p => (
                                        <option key={p.id} value={p.id} className="bg-emerald-900">
                                            {p.name} - R$ {p.price.toFixed(2)}/mês
                                        </option>
                                    ))}
                                </select>
                            </div>

                            {editingTenant && (
                                <div>
                                    <label className="text-white/80 text-sm font-medium block mb-2">Status</label>
                                    <select
                                        value={formData.status}
                                        onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                                        className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                    >
                                        <option value="active" className="bg-emerald-900">Ativo</option>
                                        <option value="inactive" className="bg-emerald-900">Inativo</option>
                                        <option value="suspended" className="bg-emerald-900">Suspenso</option>
                                    </select>
                                </div>
                            )}

                            <div className="flex gap-3 pt-4">
                                <GlassButton
                                    type="button"
                                    variant="secondary"
                                    onClick={handleCloseModal}
                                    className="flex-1"
                                >
                                    Cancelar
                                </GlassButton>
                                <GlassButton type="submit" className="flex-1">
                                    {editingTenant ? 'Salvar' : 'Criar Tenant'}
                                </GlassButton>
                            </div>
                        </form>
                    </GlassCard>
                </div>
            )}
        </div>
    );
};

export default TenantsPage;
