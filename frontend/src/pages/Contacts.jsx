import React, { useEffect, useState, useCallback } from 'react';
import {
    Search,
    Plus,
    Edit2,
    Phone,
    Mail,
    Tag,
    User,
    X,
    MessageSquare,
    ExternalLink,
    Filter,
    RefreshCw,
    Trash2,
    ChevronLeft,
    ChevronRight,
    List,
    LayoutGrid
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from '../components/ui/glass-toaster';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { ContactsAPI } from '../lib/api';
import { useNavigate } from 'react-router-dom';

const getInitials = (name) => {
    const safe = (name || '').trim();
    if (!safe) return '?';
    const parts = safe.split(/\s+/).filter(Boolean);
    const first = parts[0]?.[0] || '';
    const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || '';
    return (first + last).toUpperCase() || '?';
};

const ContactAvatar = ({ name, className }) => {
    return (
        <div
            className={cn(
                'w-12 h-12 rounded-full flex items-center justify-center bg-emerald-500/20 text-emerald-400 font-semibold select-none',
                className
            )}
        >
            <span className="text-lg">{getInitials(name)}</span>
        </div>
    );
};

const Contacts = () => {
    const { user } = useAuthStore();
    const { selectedTenant, tenants, fetchTenants, setSelectedTenant } = useAppStore();
    const navigate = useNavigate();
    const tenantId = user?.role === 'superadmin'
        ? (selectedTenant?.id || tenants?.[0]?.id || null)
        : (user?.tenantId || null);

    const [contacts, setContacts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [selectedContact, setSelectedContact] = useState(null);
    const [total, setTotal] = useState(0);
    const [offset, setOffset] = useState(0);
    const limit = 20;

    // Form states
    const [formName, setFormName] = useState('');
    const [formPhone, setFormPhone] = useState('');
    const [formEmail, setFormEmail] = useState('');
    const [formTags, setFormTags] = useState('');
    const [formCustomFields, setFormCustomFields] = useState([]);
    const [formStatus, setFormStatus] = useState('pending');
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    const [viewMode, setViewMode] = useState('list');

    // Load contacts
    const loadContacts = useCallback(async (search = '', pageOffset = 0) => {
        try {
            setLoading(true);
            if (!tenantId) {
                setContacts([]);
                setTotal(0);
                setOffset(pageOffset);
                toast.error('Tenant não identificado');
                return;
            }
            const data = await ContactsAPI.list(tenantId, search, limit, pageOffset);
            setContacts(data.contacts || []);
            setTotal(data.total || 0);
            setOffset(pageOffset);
        } catch (error) {
            console.error('Error loading contacts:', error);
            toast.error('Erro ao carregar contatos');
        } finally {
            setLoading(false);
        }
    }, [tenantId, limit]);

    useEffect(() => {
        if (user?.role !== 'superadmin') return;
        if (selectedTenant || (tenants && tenants.length > 0)) return;
        fetchTenants();
    }, [user?.role, selectedTenant, tenants, fetchTenants]);

    useEffect(() => {
        if (user?.role !== 'superadmin') return;
        if (selectedTenant) return;
        if (tenants && tenants.length > 0) setSelectedTenant(tenants[0]);
    }, [user?.role, selectedTenant, tenants, setSelectedTenant]);

    useEffect(() => {
        loadContacts(searchQuery, 0);
    }, [loadContacts]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            loadContacts(searchQuery, 0);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, loadContacts]);

    const handleCreateContact = () => {
        setFormName('');
        setFormPhone('');
        setFormEmail('');
        setFormTags('');
        setFormCustomFields([]);
        setFormStatus('verified');
        setShowCreateModal(true);
    };

    const handleEditContact = (contact) => {
        setSelectedContact(contact);
        setFormName(contact.name || '');
        setFormPhone(contact.phone || '');
        setFormEmail(contact.email || '');
        setFormTags((contact.tags || []).join(', '));
        setFormCustomFields(
            Object.entries(contact.customFields || {}).map(([key, value]) => ({ key, value }))
        );
        setFormStatus(String(contact.status || '').trim() || 'pending');
        setShowEditModal(true);
    };

    const handleSaveCreate = async () => {
        if (!formName.trim()) {
            toast.error('Nome é obrigatório');
            return;
        }
        if (!formPhone.trim()) {
            toast.error('Telefone é obrigatório');
            return;
        }

        setSaving(true);
        try {
            const tags = formTags.split(',').map(t => t.trim()).filter(Boolean);
            const customFields = {};
            formCustomFields.forEach(cf => {
                if (cf.key.trim()) {
                    customFields[cf.key.trim()] = cf.value;
                }
            });

            await ContactsAPI.create(tenantId, {
                name: formName.trim(),
                phone: formPhone.trim(),
                email: formEmail.trim() || null,
                tags,
                custom_fields: customFields,
                status: formStatus
            });

            toast.success('Contato criado com sucesso!');
            setShowCreateModal(false);
            loadContacts(searchQuery, offset);
        } catch (error) {
            toast.error(error.message || 'Erro ao criar contato');
        } finally {
            setSaving(false);
        }
    };

    const handleSaveEdit = async () => {
        if (!formName.trim()) {
            toast.error('Nome é obrigatório');
            return;
        }
        if (!selectedContact?.id) return;

        setSaving(true);
        try {
            const tags = formTags.split(',').map(t => t.trim()).filter(Boolean);
            const customFields = {};
            formCustomFields.forEach(cf => {
                if (cf.key.trim()) {
                    customFields[cf.key.trim()] = cf.value;
                }
            });

            await ContactsAPI.update(selectedContact.id, {
                full_name: formName.trim(),
                email: formEmail.trim() || null,
                tags,
                custom_fields: customFields,
                status: formStatus
            });

            toast.success('Contato atualizado com sucesso!');
            setShowEditModal(false);
            loadContacts(searchQuery, offset);
        } catch (error) {
            if (error.response?.status === 404) {
                toast.error('Contato não encontrado. Ele pode ter sido excluído.');
                setShowEditModal(false);
                loadContacts(searchQuery, offset);
            } else {
                toast.error(error.message || 'Erro ao atualizar contato');
            }
        } finally {
            setSaving(false);
        }
    };

    const handleAddCustomField = () => {
        setFormCustomFields([...formCustomFields, { key: '', value: '' }]);
    };

    const handleRemoveCustomField = (index) => {
        setFormCustomFields(formCustomFields.filter((_, i) => i !== index));
    };

    const handleCustomFieldChange = (index, field, value) => {
        const updated = [...formCustomFields];
        updated[index][field] = value;
        setFormCustomFields(updated);
    };

    const handleViewInInbox = (contact) => {
        // Navigate to inbox with contact phone as filter
        const phone = String(contact?.phone || '').replace(/\D/g, '');
        const contactId = contact?.id ? String(contact.id) : '';
        const params = new URLSearchParams();
        params.set('search', phone);
        if (contactId) params.set('contactId', contactId);
        navigate(`/app/inbox?${params.toString()}`);
    };

    const handleDeleteContact = async (contact) => {
        const contactId = contact?.id ? String(contact.id) : '';
        if (!contactId) return;

        const displayName = String(contact?.name || '').trim() || String(contact?.phone || '').trim() || 'este contato';
        const ok = window.confirm(`Excluir contato "${displayName}"?`);
        if (!ok) return;

        setDeletingId(contactId);
        try {
            await ContactsAPI.delete(contactId);
            toast.success('Contato excluído com sucesso!');

            const isLastItemOnPage = (contacts || []).length === 1;
            const nextOffset = isLastItemOnPage ? Math.max(0, offset - limit) : offset;
            loadContacts(searchQuery, nextOffset);
        } catch (error) {
            toast.error(error.message || 'Erro ao excluir contato');
        } finally {
            setDeletingId(null);
        }
    };

    const formatDate = (date) => {
        try {
            return formatDistanceToNow(new Date(date), { addSuffix: true, locale: ptBR });
        } catch {
            return '';
        }
    };

    const formatContactStatus = (value) => {
        const s = String(value || '').trim().toLowerCase();
        if (s === 'verified') return { label: 'Verificado', variant: 'success' };
        if (s === 'unverified') return { label: 'Não verificado', variant: 'warning' };
        return { label: 'Pendente', variant: 'warning' };
    };

    const totalPages = Math.ceil(total / limit);
    const currentPage = Math.floor(offset / limit) + 1;

    return (
        <div className="h-full min-h-0 flex flex-col p-4 lg:p-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white">Contatos</h1>
                    <p className="text-white/60 text-sm mt-1">
                        {total} contato{total !== 1 ? 's' : ''} encontrado{total !== 1 ? 's' : ''}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center rounded-xl bg-white/5 p-1">
                        <button
                            type="button"
                            onClick={() => setViewMode('list')}
                            aria-pressed={viewMode === 'list'}
                            className={cn(
                                'p-2 rounded-lg transition-colors',
                                viewMode === 'list'
                                    ? 'bg-white/10 text-white'
                                    : 'text-white/60 hover:bg-white/10 hover:text-white'
                            )}
                            title="Lista"
                        >
                            <List className="w-4 h-4" />
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode('grid')}
                            aria-pressed={viewMode === 'grid'}
                            className={cn(
                                'p-2 rounded-lg transition-colors',
                                viewMode === 'grid'
                                    ? 'bg-white/10 text-white'
                                    : 'text-white/60 hover:bg-white/10 hover:text-white'
                            )}
                            title="Grade"
                        >
                            <LayoutGrid className="w-4 h-4" />
                        </button>
                    </div>
                    <GlassButton
                        onClick={handleCreateContact}
                        className="flex items-center gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        Novo Contato
                    </GlassButton>
                </div>
            </div>

            {/* Search */}
            <div className="relative mb-6">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <GlassInput
                    type="text"
                    placeholder="Buscar por nome, telefone ou email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 py-2.5"
                />
            </div>

            {/* Contacts List */}
            <div className="flex-1 min-h-0 overflow-y-auto">
                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
                    </div>
                ) : contacts.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-white/50">
                        <User className="w-16 h-16 mb-4 opacity-50" />
                        <p className="text-lg font-medium">Nenhum contato encontrado</p>
                        <p className="text-sm mt-1">Clique em "Novo Contato" para adicionar</p>
                    </div>
                ) : (
                    <div
                        className={cn(
                            'grid',
                            viewMode === 'grid'
                                ? 'gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4'
                                : 'gap-3 grid-cols-1'
                        )}
                    >
                        {contacts.map((contact) => (
                            <GlassCard
                                key={contact.id}
                                className={cn(
                                    'p-4 hover:bg-white/5 transition-colors cursor-pointer',
                                    viewMode === 'grid' ? 'h-full' : ''
                                )}
                                onClick={() => handleEditContact(contact)}
                            >
                                {viewMode === 'grid' ? (
                                    <div className="flex flex-col h-full">
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="flex items-center gap-3 min-w-0">
                                                <ContactAvatar name={contact.name} className="w-11 h-11" />
                                                <div className="min-w-0">
                                                    <h3 className="font-semibold text-white truncate">
                                                        {contact.name || 'Sem nome'}
                                                    </h3>
                                                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                                                        {contact.status && (
                                                            <GlassBadge
                                                                variant={formatContactStatus(contact.status).variant}
                                                                className="px-2 py-0.5 text-xs"
                                                            >
                                                                {formatContactStatus(contact.status).label}
                                                            </GlassBadge>
                                                        )}
                                                        {contact.source && (
                                                            <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-white/60">
                                                                {contact.source}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleViewInInbox(contact);
                                                    }}
                                                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                    title="Ver conversas"
                                                >
                                                    <MessageSquare className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleEditContact(contact);
                                                    }}
                                                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                    title="Editar contato"
                                                >
                                                    <Edit2 className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteContact(contact);
                                                    }}
                                                    disabled={deletingId === String(contact.id)}
                                                    className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                    title="Excluir contato"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>

                                        <div className="mt-4 text-sm text-white/60 space-y-2">
                                            <div className="flex items-center gap-2">
                                                <Phone className="w-3.5 h-3.5 shrink-0" />
                                                <span className="truncate">{contact.phone}</span>
                                            </div>
                                            {contact.email && (
                                                <div className="flex items-center gap-2">
                                                    <Mail className="w-3.5 h-3.5 shrink-0" />
                                                    <span className="truncate">{contact.email}</span>
                                                </div>
                                            )}
                                        </div>

                                        {contact.tags && contact.tags.length > 0 && (
                                            <div className="flex items-center gap-1 mt-4 flex-wrap">
                                                {contact.tags.slice(0, 3).map((tag, i) => (
                                                    <GlassBadge
                                                        key={i}
                                                        variant="success"
                                                        className="px-2 py-0.5 text-xs"
                                                    >
                                                        {tag}
                                                    </GlassBadge>
                                                ))}
                                                {contact.tags.length > 3 && (
                                                    <span className="text-xs text-white/40">
                                                        +{contact.tags.length - 3}
                                                    </span>
                                                )}
                                            </div>
                                        )}

                                        {(contact.firstContactAt || contact.createdAt) && (
                                            <p className="text-xs text-white/40 mt-4">
                                                1º contato {formatDate(contact.firstContactAt || contact.createdAt)}
                                            </p>
                                        )}
                                    </div>
                                ) : (
                                    <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                                        <div className="flex items-center gap-4 min-w-0 flex-1">
                                            <ContactAvatar name={contact.name} />
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <h3 className="font-semibold text-white truncate">
                                                        {contact.name || 'Sem nome'}
                                                    </h3>
                                                    {contact.status && (
                                                        <GlassBadge
                                                            variant={formatContactStatus(contact.status).variant}
                                                            className="px-2 py-0.5 text-xs"
                                                        >
                                                            {formatContactStatus(contact.status).label}
                                                        </GlassBadge>
                                                    )}
                                                    {contact.source && (
                                                        <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-white/60">
                                                            {contact.source}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 mt-1 text-sm text-white/60">
                                                    <span className="flex items-center gap-1 min-w-0">
                                                        <Phone className="w-3.5 h-3.5 shrink-0" />
                                                        <span className="truncate">{contact.phone}</span>
                                                    </span>
                                                    {contact.email && (
                                                        <span className="flex items-center gap-1 min-w-0">
                                                            <Mail className="w-3.5 h-3.5 shrink-0" />
                                                            <span className="truncate">{contact.email}</span>
                                                        </span>
                                                    )}
                                                </div>
                                                {contact.tags && contact.tags.length > 0 && (
                                                    <div className="flex items-center gap-1 mt-2 flex-wrap">
                                                        {contact.tags.slice(0, 3).map((tag, i) => (
                                                            <GlassBadge
                                                                key={i}
                                                                variant="success"
                                                                className="px-2 py-0.5 text-xs"
                                                            >
                                                                {tag}
                                                            </GlassBadge>
                                                        ))}
                                                        {contact.tags.length > 3 && (
                                                            <span className="text-xs text-white/40">
                                                                +{contact.tags.length - 3}
                                                            </span>
                                                        )}
                                                    </div>
                                                )}
                                                {(contact.firstContactAt || contact.createdAt) && (
                                                    <p className="text-xs text-white/40 mt-2">
                                                        1º contato {formatDate(contact.firstContactAt || contact.createdAt)}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleViewInInbox(contact);
                                                }}
                                                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                title="Ver conversas"
                                            >
                                                <MessageSquare className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleEditContact(contact);
                                                }}
                                                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                                                title="Editar contato"
                                            >
                                                <Edit2 className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDeleteContact(contact);
                                                }}
                                                disabled={deletingId === String(contact.id)}
                                                className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                title="Excluir contato"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </GlassCard>
                        ))}
                    </div>
                )}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-4 mt-4 pt-4 border-t border-white/10">
                    <button
                        onClick={() => loadContacts(searchQuery, Math.max(0, offset - limit))}
                        disabled={offset === 0}
                        className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <span className="text-white/60 text-sm">
                        Página {currentPage} de {totalPages}
                    </span>
                    <button
                        onClick={() => loadContacts(searchQuery, offset + limit)}
                        disabled={currentPage >= totalPages}
                        className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>
            )}

            {/* Create Contact Modal */}
            <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
                <DialogContent className="max-w-lg">
                    <div className="p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <Plus className="w-5 h-5 text-emerald-400" />
                                Novo Contato
                            </h2>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-2 rounded-lg hover:bg-white/10 text-white/60"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Nome *
                                </label>
                                <GlassInput
                                    value={formName}
                                    onChange={(e) => setFormName(e.target.value)}
                                    placeholder="Nome do contato"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Telefone *
                                </label>
                                <GlassInput
                                    value={formPhone}
                                    onChange={(e) => setFormPhone(e.target.value)}
                                    placeholder="5521999999999"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Email
                                </label>
                                <GlassInput
                                    type="email"
                                    value={formEmail}
                                    onChange={(e) => setFormEmail(e.target.value)}
                                    placeholder="email@exemplo.com"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Status
                                </label>
                                <select
                                    value={formStatus}
                                    onChange={(e) => setFormStatus(e.target.value)}
                                    className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                >
                                    <option value="pending" className="bg-emerald-900">Pendente</option>
                                    <option value="unverified" className="bg-emerald-900">Não verificado</option>
                                    <option value="verified" className="bg-emerald-900">Verificado</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Tags (separadas por vírgula)
                                </label>
                                <GlassInput
                                    value={formTags}
                                    onChange={(e) => setFormTags(e.target.value)}
                                    placeholder="cliente, vip, ativo"
                                />
                            </div>

                            {/* Custom Fields */}
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <label className="text-sm font-medium text-white/70">
                                        Campos Personalizados
                                    </label>
                                    <button
                                        onClick={handleAddCustomField}
                                        className="text-xs text-emerald-400 hover:text-emerald-500 flex items-center gap-1"
                                    >
                                        <Plus className="w-3 h-3" />
                                        Adicionar
                                    </button>
                                </div>
                                {formCustomFields.map((cf, index) => (
                                    <div key={index} className="flex gap-2 mb-2">
                                        <GlassInput
                                            value={cf.key}
                                            onChange={(e) => handleCustomFieldChange(index, 'key', e.target.value)}
                                            placeholder="Campo"
                                            className="flex-1"
                                        />
                                        <GlassInput
                                            value={cf.value}
                                            onChange={(e) => handleCustomFieldChange(index, 'value', e.target.value)}
                                            placeholder="Valor"
                                            className="flex-1"
                                        />
                                        <button
                                            onClick={() => handleRemoveCustomField(index)}
                                            className="p-2 rounded-lg hover:bg-red-500/20 text-red-400"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))}
                            </div>

                            <div className="flex justify-end gap-3 pt-4">
                                <GlassButton
                                    variant="secondary"
                                    onClick={() => setShowCreateModal(false)}
                                >
                                    Cancelar
                                </GlassButton>
                                <GlassButton onClick={handleSaveCreate} disabled={saving}>
                                    {saving ? 'Salvando...' : 'Criar Contato'}
                                </GlassButton>
                            </div>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Edit Contact Modal */}
            <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
                <DialogContent className="max-w-lg">
                    <div className="p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <Edit2 className="w-5 h-5 text-emerald-400" />
                                Editar Contato
                            </h2>
                            <button
                                onClick={() => setShowEditModal(false)}
                                className="p-2 rounded-lg hover:bg-white/10 text-white/60"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Nome *
                                </label>
                                <GlassInput
                                    value={formName}
                                    onChange={(e) => setFormName(e.target.value)}
                                    placeholder="Nome do contato"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Telefone
                                </label>
                                <GlassInput
                                    value={formPhone}
                                    disabled
                                    className="opacity-60 cursor-not-allowed"
                                />
                                <p className="text-xs text-white/40 mt-1">
                                    O telefone não pode ser alterado
                                </p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Email
                                </label>
                                <GlassInput
                                    type="email"
                                    value={formEmail}
                                    onChange={(e) => setFormEmail(e.target.value)}
                                    placeholder="email@exemplo.com"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/70 mb-1.5">
                                    Tags (separadas por vírgula)
                                </label>
                                <GlassInput
                                    value={formTags}
                                    onChange={(e) => setFormTags(e.target.value)}
                                    placeholder="cliente, vip, ativo"
                                />
                            </div>

                            {/* Custom Fields */}
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <label className="text-sm font-medium text-white/70">
                                        Campos Personalizados
                                    </label>
                                    <button
                                        onClick={handleAddCustomField}
                                        className="text-xs text-emerald-400 hover:text-emerald-500 flex items-center gap-1"
                                    >
                                        <Plus className="w-3 h-3" />
                                        Adicionar
                                    </button>
                                </div>
                                {formCustomFields.map((cf, index) => (
                                    <div key={index} className="flex gap-2 mb-2">
                                        <GlassInput
                                            value={cf.key}
                                            onChange={(e) => handleCustomFieldChange(index, 'key', e.target.value)}
                                            placeholder="Campo"
                                            className="flex-1"
                                        />
                                        <GlassInput
                                            value={cf.value}
                                            onChange={(e) => handleCustomFieldChange(index, 'value', e.target.value)}
                                            placeholder="Valor"
                                            className="flex-1"
                                        />
                                        <button
                                            onClick={() => handleRemoveCustomField(index)}
                                            className="p-2 rounded-lg hover:bg-red-500/20 text-red-400"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))}
                            </div>

                            {selectedContact?.createdAt && (
                                <p className="text-xs text-white/40 pt-2">
                                    Criado {formatDate(selectedContact.createdAt)}
                                </p>
                            )}
                            {selectedContact?.firstContactAt && (
                                <p className="text-xs text-white/40">
                                    1º contato {formatDate(selectedContact.firstContactAt)}
                                </p>
                            )}

                            <div className="flex justify-end gap-3 pt-4">
                                <GlassButton
                                    variant="secondary"
                                    onClick={() => setShowEditModal(false)}
                                >
                                    Cancelar
                                </GlassButton>
                                <GlassButton onClick={handleSaveEdit} disabled={saving}>
                                    {saving ? 'Salvando...' : 'Salvar Alterações'}
                                </GlassButton>
                            </div>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default Contacts;
