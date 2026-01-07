import React, { useEffect, useState } from 'react';
import {
    CreditCard,
    Plus,
    Search,
    Edit,
    Trash2,
    X,
    Check,
    MessageSquare,
    Users,
    Plug,
    TrendingUp
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';
import { PlansAPI } from '../lib/api';

const PlansPage = () => {
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [editingPlan, setEditingPlan] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        slug: '',
        price: 0,
        max_instances: 1,
        max_messages_month: 1000,
        max_users: 1,
        features: {
            chatbot: false,
            automations: false,
            kb: true,
            api: false,
            whitelabel: false
        },
        is_active: true
    });

    useEffect(() => {
        fetchPlans();
    }, []);

    const fetchPlans = async () => {
        setLoading(true);
        try {
            const data = await PlansAPI.list();
            setPlans(data);
        } catch (error) {
            console.error('Error fetching plans:', error);
            toast.error('Erro ao carregar planos');
        } finally {
            setLoading(false);
        }
    };

    const filteredPlans = plans.filter(plan =>
        plan.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        plan.slug.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleOpenModal = (plan = null) => {
        if (plan) {
            setEditingPlan(plan);
            setFormData({
                name: plan.name,
                slug: plan.slug,
                price: plan.price,
                max_instances: plan.maxInstances,
                max_messages_month: plan.maxMessagesMonth,
                max_users: plan.maxUsers,
                features: plan.features || {},
                is_active: plan.isActive
            });
        } else {
            setEditingPlan(null);
            setFormData({
                name: '',
                slug: '',
                price: 0,
                max_instances: 1,
                max_messages_month: 1000,
                max_users: 1,
                features: {
                    chatbot: false,
                    automations: false,
                    kb: true,
                    api: false,
                    whitelabel: false
                },
                is_active: true
            });
        }
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setEditingPlan(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            if (editingPlan) {
                await PlansAPI.update(editingPlan.id, formData);
                toast.success('Plano atualizado!');
            } else {
                await PlansAPI.create(formData);
                toast.success('Plano criado!');
            }
            handleCloseModal();
            fetchPlans();
        } catch (error) {
            console.error('Error saving plan:', error);
            toast.error('Erro ao salvar plano');
        }
    };

    const handleDelete = async (id, name) => {
        if (window.confirm(`Tem certeza que deseja excluir o plano "${name}"?`)) {
            try {
                await PlansAPI.delete(id);
                toast.success('Plano excluído!');
                fetchPlans();
            } catch (error) {
                console.error('Error deleting plan:', error);
                toast.error(error.response?.data?.detail || 'Erro ao excluir plano');
            }
        }
    };

    const handleSlugGeneration = (name) => {
        const slug = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
        setFormData(prev => ({ ...prev, name, slug }));
    };

    const toggleFeature = (feature) => {
        setFormData(prev => ({
            ...prev,
            features: {
                ...prev.features,
                [feature]: !prev.features[feature]
            }
        }));
    };

    const formatPrice = (price) => {
        return price === 0 ? 'Grátis' : `R$ ${price.toFixed(2)}`;
    };

    const formatLimit = (value) => {
        return value === 0 ? 'Ilimitado' : value.toLocaleString();
    };

    return (
        <div className="min-h-screen p-6 lg:p-8">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Gerenciar Planos</h1>
                <p className="text-white/60">Configure os planos disponíveis para os tenants</p>
            </div>

            {/* Filters and Actions */}
            <div className="flex flex-col lg:flex-row gap-4 mb-6">
                <div className="flex-1 relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                    <GlassInput
                        type="text"
                        placeholder="Pesquisar planos..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-12"
                    />
                </div>
                <GlassButton onClick={() => handleOpenModal()} className="flex items-center gap-2">
                    <Plus className="w-5 h-5" />
                    <span className="hidden sm:inline">Novo Plano</span>
                </GlassButton>
            </div>

            {/* Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {loading ? (
                    <div className="col-span-full text-center py-12">
                        <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                        <p className="text-white/60">Carregando planos...</p>
                    </div>
                ) : filteredPlans.length === 0 ? (
                    <div className="col-span-full text-center py-12">
                        <CreditCard className="w-16 h-16 text-white/20 mx-auto mb-4" />
                        <p className="text-white/60">Nenhum plano encontrado</p>
                    </div>
                ) : (
                    filteredPlans.map((plan) => (
                        <GlassCard key={plan.id} className="p-6 flex flex-col">
                            <div className="flex items-start justify-between mb-4">
                                <div>
                                    <h3 className="text-xl font-bold text-white">{plan.name}</h3>
                                    <p className="text-white/50 text-sm">/{plan.slug}</p>
                                </div>
                                <GlassBadge variant={plan.isActive ? 'success' : 'warning'}>
                                    {plan.isActive ? 'Ativo' : 'Inativo'}
                                </GlassBadge>
                            </div>

                            <div className="text-3xl font-bold text-emerald-400 mb-6">
                                {formatPrice(plan.price)}
                                {plan.price > 0 && <span className="text-sm text-white/50 font-normal">/mês</span>}
                            </div>

                            <div className="space-y-3 flex-1">
                                <div className="flex items-center gap-3 text-white/80">
                                    <Plug className="w-4 h-4 text-emerald-400" />
                                    <span>{formatLimit(plan.maxInstances)} conexões</span>
                                </div>
                                <div className="flex items-center gap-3 text-white/80">
                                    <MessageSquare className="w-4 h-4 text-blue-400" />
                                    <span>{formatLimit(plan.maxMessagesMonth)} msgs/mês</span>
                                </div>
                                <div className="flex items-center gap-3 text-white/80">
                                    <Users className="w-4 h-4 text-purple-400" />
                                    <span>{formatLimit(plan.maxUsers)} usuários</span>
                                </div>
                            </div>

                            {/* Features */}
                            <div className="mt-4 pt-4 border-t border-white/10">
                                <div className="flex flex-wrap gap-2">
                                    {Object.entries(plan.features || {}).map(([key, value]) => (
                                        <GlassBadge
                                            key={key}
                                            variant={value ? 'success' : 'danger'}
                                            className={cn('px-2 py-1 text-xs font-medium rounded', !value && 'line-through')}
                                        >
                                            {key}
                                        </GlassBadge>
                                    ))}
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex gap-2 mt-4 pt-4 border-t border-white/10">
                                <GlassButton
                                    onClick={() => handleOpenModal(plan)}
                                    variant="secondary"
                                    className="flex-1 flex items-center justify-center gap-2"
                                >
                                    <Edit className="w-4 h-4" />
                                    Editar
                                </GlassButton>
                                <button
                                    onClick={() => handleDelete(plan.id, plan.name)}
                                    className="p-2 rounded-lg hover:bg-red-500/20 text-white/60 hover:text-red-400 transition-colors"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                        </GlassCard>
                    ))
                )}
            </div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <GlassCard className="w-full max-w-lg max-h-[90vh] overflow-y-auto" hover={false}>
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white">
                                {editingPlan ? 'Editar Plano' : 'Novo Plano'}
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
                                <label className="text-white/80 text-sm font-medium block mb-2">Nome do Plano</label>
                                <GlassInput
                                    type="text"
                                    placeholder="Ex: Pro"
                                    value={formData.name}
                                    onChange={(e) => handleSlugGeneration(e.target.value)}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Slug</label>
                                <GlassInput
                                    type="text"
                                    placeholder="Ex: pro"
                                    value={formData.slug}
                                    onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Preço Mensal (R$)</label>
                                <GlassInput
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    placeholder="0.00"
                                    value={formData.price}
                                    onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) || 0 })}
                                />
                            </div>

                            <div className="grid grid-cols-3 gap-4">
                                <div>
                                    <label className="text-white/80 text-sm font-medium block mb-2">Conexões</label>
                                    <GlassInput
                                        type="number"
                                        min="0"
                                        placeholder="0 = ilimitado"
                                        value={formData.max_instances}
                                        onChange={(e) => setFormData({ ...formData, max_instances: parseInt(e.target.value) || 0 })}
                                    />
                                </div>
                                <div>
                                    <label className="text-white/80 text-sm font-medium block mb-2">Msgs/Mês</label>
                                    <GlassInput
                                        type="number"
                                        min="0"
                                        placeholder="0 = ilimitado"
                                        value={formData.max_messages_month}
                                        onChange={(e) => setFormData({ ...formData, max_messages_month: parseInt(e.target.value) || 0 })}
                                    />
                                </div>
                                <div>
                                    <label className="text-white/80 text-sm font-medium block mb-2">Usuários</label>
                                    <GlassInput
                                        type="number"
                                        min="0"
                                        placeholder="0 = ilimitado"
                                        value={formData.max_users}
                                        onChange={(e) => setFormData({ ...formData, max_users: parseInt(e.target.value) || 0 })}
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Recursos</label>
                                <div className="grid grid-cols-2 gap-2">
                                    {['chatbot', 'automations', 'kb', 'api', 'whitelabel'].map((feature) => (
                                        <button
                                            key={feature}
                                            type="button"
                                            onClick={() => toggleFeature(feature)}
                                            className={cn(
                                                'flex items-center gap-2 px-3 py-2 rounded-lg transition-colors',
                                                formData.features[feature]
                                                    ? 'bg-emerald-500/20 text-emerald-400'
                                                    : 'bg-white/5 text-white/60 hover:bg-white/10'
                                            )}
                                        >
                                            {formData.features[feature] ? (
                                                <Check className="w-4 h-4" />
                                            ) : (
                                                <X className="w-4 h-4" />
                                            )}
                                            <span className="capitalize">{feature}</span>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={() => setFormData({ ...formData, is_active: !formData.is_active })}
                                    className={cn(
                                        'w-12 h-6 rounded-full transition-colors',
                                        formData.is_active ? 'bg-emerald-500' : 'bg-white/20'
                                    )}
                                >
                                    <div
                                        className={cn(
                                            'w-5 h-5 rounded-full bg-white shadow-lg transition-transform',
                                            formData.is_active ? 'translate-x-6' : 'translate-x-0.5'
                                        )}
                                    />
                                </button>
                                <label className="text-white/80 text-sm">Plano ativo</label>
                            </div>

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
                                    {editingPlan ? 'Salvar' : 'Criar Plano'}
                                </GlassButton>
                            </div>
                        </form>
                    </GlassCard>
                </div>
            )}
        </div>
    );
};

export default PlansPage;
