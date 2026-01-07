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
    ChevronRight
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
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
    const navigate = useNavigate();
    const tenantId = user?.tenantId || 'tenant-1';

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
    const [saving, setSaving] = useState(false);

    // Load contacts
    const loadContacts = useCallback(async (search = '', pageOffset = 0) => {
        try {
            setLoading(true);
            const data = await ContactsAPI.list(search, limit, pageOffset);
            setContacts(data.contacts || []);
            setTotal(data.total || 0);
            setOffset(pageOffset);
        } catch (error) {
            console.error('Error loading contacts:', error);
            toast.error('Erro ao carregar contatos');
        } finally {
            setLoading(false);
        }
    }, []);

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

            await ContactsAPI.create({
                name: formName.trim(),
                phone: formPhone.trim(),
                email: formEmail.trim() || null,
                tags,
                custom_fields: customFields
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
                custom_fields: customFields
            });

            toast.success('Contato atualizado com sucesso!');
            setShowEditModal(false);
            loadContacts(searchQuery, offset);
        } catch (error) {
            toast.error(error.message || 'Erro ao atualizar contato');
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
        navigate(`/app/inbox?search=${encodeURIComponent(phone)}`);
    };

    const formatDate = (date) => {
        try {
            return formatDistanceToNow(new Date(date), { addSuffix: true, locale: ptBR });
        } catch {
            return '';
        }
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
                <GlassButton
                    onClick={handleCreateContact}
                    className="flex items-center gap-2"
                >
                    <Plus className="w-4 h-4" />
                    Novo Contato
                </GlassButton>
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
                    <div className="grid gap-3">
                        {contacts.map((contact) => (
                            <GlassCard
                                key={contact.id}
                                className="p-4 hover:bg-white/5 transition-colors cursor-pointer"
                                onClick={() => handleEditContact(contact)}
                            >
                                <div className="flex items-center gap-4">
                                    <ContactAvatar name={contact.name} />
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <h3 className="font-semibold text-white truncate">
                                                {contact.name || 'Sem nome'}
                                            </h3>
                                            {contact.source && (
                                                <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-white/60">
                                                    {contact.source}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-3 mt-1 text-sm text-white/60">
                                            <span className="flex items-center gap-1">
                                                <Phone className="w-3.5 h-3.5" />
                                                {contact.phone}
                                            </span>
                                            {contact.email && (
                                                <span className="flex items-center gap-1">
                                                    <Mail className="w-3.5 h-3.5" />
                                                    {contact.email}
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
                                    </div>
                                </div>
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
