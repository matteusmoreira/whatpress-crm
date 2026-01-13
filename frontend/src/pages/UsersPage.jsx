import React, { useEffect, useState } from 'react';
import {
    Users,
    Plus,
    Search,
    Edit,
    Trash2,
    X,
    Building2,
    Shield,
    UserCheck
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';
import { UsersAPI, TenantsAPI } from '../lib/api';

const UsersPage = () => {
    const [users, setUsers] = useState([]);
    const [tenants, setTenants] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [roleFilter, setRoleFilter] = useState('all');
    const [tenantFilter, setTenantFilter] = useState('all');
    const [showModal, setShowModal] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: '',
        role: 'agent',
        tenant_id: ''
    });

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [usersData, tenantsData] = await Promise.all([
                UsersAPI.list(),
                TenantsAPI.list()
            ]);
            setUsers(usersData);
            setTenants(tenantsData);
        } catch (error) {
            console.error('Error fetching data:', error);
            toast.error('Erro ao carregar dados');
        } finally {
            setLoading(false);
        }
    };

    const filteredUsers = users.filter(user => {
        const matchesSearch =
            user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.email.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesRole = roleFilter === 'all' || user.role === roleFilter;
        const matchesTenant = tenantFilter === 'all' || user.tenantId === tenantFilter || (tenantFilter === 'none' && !user.tenantId);
        return matchesSearch && matchesRole && matchesTenant;
    });

    const handleOpenModal = (user = null) => {
        if (user) {
            setEditingUser(user);
            setFormData({
                name: user.name,
                email: user.email,
                password: '',
                role: user.role,
                tenant_id: user.tenantId || ''
            });
        } else {
            setEditingUser(null);
            setFormData({
                name: '',
                email: '',
                password: '',
                role: 'agent',
                tenant_id: ''
            });
        }
        setShowModal(true);
    };

    const handleCloseModal = () => {
        setShowModal(false);
        setEditingUser(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const data = { ...formData };
            // Remove password if empty (for edit)
            if (!data.password) {
                delete data.password;
            }
            // Convert empty tenant_id to null
            if (!data.tenant_id) {
                data.tenant_id = null;
            }

            if (editingUser) {
                await UsersAPI.update(editingUser.id, data);
                toast.success('Usuário atualizado!');
            } else {
                if (!formData.password) {
                    toast.error('Senha é obrigatória para novos usuários');
                    return;
                }
                await UsersAPI.create(data);
                toast.success('Usuário criado!');
            }
            handleCloseModal();
            fetchData();
        } catch (error) {
            console.error('Error saving user:', error);
            toast.error(error.response?.data?.detail || 'Erro ao salvar usuário');
        }
    };

    const handleDelete = async (id, name) => {
        if (window.confirm(`Tem certeza que deseja excluir o usuário "${name}"?`)) {
            try {
                await UsersAPI.delete(id);
                toast.success('Usuário excluído!');
                fetchData();
            } catch (error) {
                console.error('Error deleting user:', error);
                toast.error(error.response?.data?.detail || 'Erro ao excluir usuário');
            }
        }
    };

    const getRoleBadge = (role) => {
        const variants = {
            superadmin: { variant: 'danger', label: 'Super Admin', icon: Shield },
            admin: { variant: 'warning', label: 'Admin', icon: UserCheck },
            agent: { variant: 'info', label: 'Agente', icon: Users }
        };
        const config = variants[role] || variants.agent;
        return (
            <GlassBadge variant={config.variant} className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium">
                <config.icon className="w-3 h-3" />
                {config.label}
            </GlassBadge>
        );
    };

    return (
        <div className="min-h-screen p-4 sm:p-6 lg:p-8">
            {/* Header */}
            <div className="mb-8 pl-16 lg:pl-0">
                <h1 className="wa-page-title">Gerenciar Usuários</h1>
                <p className="wa-page-subtitle">Crie e gerencie usuários do sistema</p>
            </div>

            {/* Filters and Actions */}
            <div className="flex flex-col lg:flex-row gap-4 mb-6">
                <div className="flex-1 relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
                    <GlassInput
                        type="text"
                        placeholder="Pesquisar usuários..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-12"
                    />
                </div>
                <div className="flex gap-3">
                    <select
                        value={roleFilter}
                        onChange={(e) => setRoleFilter(e.target.value)}
                        className="h-11 px-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                    >
                        <option value="all" className="bg-emerald-900">Todos os Roles</option>
                        <option value="superadmin" className="bg-emerald-900">Super Admin</option>
                        <option value="admin" className="bg-emerald-900">Admin</option>
                        <option value="agent" className="bg-emerald-900">Agente</option>
                    </select>
                    <select
                        value={tenantFilter}
                        onChange={(e) => setTenantFilter(e.target.value)}
                        className="h-11 px-4 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                    >
                        <option value="all" className="bg-emerald-900">Todos os Tenants</option>
                        <option value="none" className="bg-emerald-900">Sem Tenant</option>
                        {tenants.map(t => (
                            <option key={t.id} value={t.id} className="bg-emerald-900">{t.name}</option>
                        ))}
                    </select>
                    <GlassButton onClick={() => handleOpenModal()} className="flex items-center gap-2">
                        <Plus className="w-5 h-5" />
                        <span className="hidden sm:inline">Novo Usuário</span>
                    </GlassButton>
                </div>
            </div>

            {/* Users Table */}
            <GlassCard className="overflow-hidden" hover={false}>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-white/10">
                                <th className="text-left p-4 text-white/60 font-medium">Usuário</th>
                                <th className="text-left p-4 text-white/60 font-medium">Email</th>
                                <th className="text-left p-4 text-white/60 font-medium">Role</th>
                                <th className="text-left p-4 text-white/60 font-medium">Tenant</th>
                                <th className="text-right p-4 text-white/60 font-medium">Ações</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-white/60">
                                        <div className="flex items-center justify-center gap-2">
                                            <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                                            Carregando...
                                        </div>
                                    </td>
                                </tr>
                            ) : filteredUsers.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-8 text-center text-white/60">
                                        Nenhum usuário encontrado
                                    </td>
                                </tr>
                            ) : (
                                filteredUsers.map((user) => (
                                    <tr
                                        key={user.id}
                                        className="border-b border-white/5 hover:bg-white/5 transition-colors"
                                    >
                                        <td className="p-4">
                                            <div className="flex items-center gap-3">
                                                <img
                                                    src={user.avatar}
                                                    alt={user.name}
                                                    className="w-10 h-10 rounded-full border-2 border-emerald-500/30"
                                                />
                                                <span className="text-white font-medium">{user.name}</span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-white/70">{user.email}</td>
                                        <td className="p-4">{getRoleBadge(user.role)}</td>
                                        <td className="p-4">
                                            {user.tenantName ? (
                                                <div className="flex items-center gap-2 text-white/70">
                                                    <Building2 className="w-4 h-4 text-emerald-400" />
                                                    {user.tenantName}
                                                </div>
                                            ) : (
                                                <span className="text-white/40 italic">Sem tenant</span>
                                            )}
                                        </td>
                                        <td className="p-4">
                                            <div className="flex items-center justify-end gap-2">
                                                <button
                                                    onClick={() => handleOpenModal(user)}
                                                    className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                >
                                                    <Edit className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(user.id, user.name)}
                                                    className="p-2 rounded-lg hover:bg-red-500/20 text-white/60 hover:text-red-400 transition-colors"
                                                    disabled={user.role === 'superadmin'}
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
                                {editingUser ? 'Editar Usuário' : 'Novo Usuário'}
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
                                <label className="text-white/80 text-sm font-medium block mb-2">Nome</label>
                                <GlassInput
                                    type="text"
                                    placeholder="Nome completo"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Email</label>
                                <GlassInput
                                    type="email"
                                    placeholder="email@exemplo.com"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    required
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">
                                    Senha {editingUser && <span className="text-white/40">(deixe vazio para manter)</span>}
                                </label>
                                <GlassInput
                                    type="password"
                                    placeholder={editingUser ? '••••••••' : 'Senha'}
                                    value={formData.password}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    required={!editingUser}
                                />
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Role</label>
                                <select
                                    value={formData.role}
                                    onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                    className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                >
                                    <option value="agent" className="bg-emerald-900">Agente</option>
                                    <option value="admin" className="bg-emerald-900">Admin</option>
                                    <option value="superadmin" className="bg-emerald-900">Super Admin</option>
                                </select>
                            </div>

                            <div>
                                <label className="text-white/80 text-sm font-medium block mb-2">Tenant</label>
                                <select
                                    value={formData.tenant_id}
                                    onChange={(e) => setFormData({ ...formData, tenant_id: e.target.value })}
                                    className="w-full px-4 py-3 rounded-xl bg-white/10 backdrop-blur-sm border border-white/20 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                >
                                    <option value="" className="bg-emerald-900">Sem tenant (SuperAdmin)</option>
                                    {tenants.map(t => (
                                        <option key={t.id} value={t.id} className="bg-emerald-900">{t.name}</option>
                                    ))}
                                </select>
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
                                    {editingUser ? 'Salvar' : 'Criar Usuário'}
                                </GlassButton>
                            </div>
                        </form>
                    </GlassCard>
                </div>
            )}
        </div>
    );
};

export default UsersPage;
