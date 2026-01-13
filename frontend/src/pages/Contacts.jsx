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
    LayoutGrid,
    Columns3,
    Settings,
    ArrowUp,
    ArrowDown
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from '../components/ui/glass-toaster';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../components/ui/dialog';
import * as VisuallyHidden from '@radix-ui/react-visually-hidden';
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

const KANBAN_UNASSIGNED_COLUMN_ID = '__unassigned__';
const KANBAN_CUSTOM_FIELD_KEY = 'kanban_column';

const DEFAULT_KANBAN_COLUMNS = [
    { id: 'novos', title: 'Novos', color: 'emerald' },
    { id: 'qualificacao', title: 'Qualificação', color: 'blue' },
    { id: 'proposta', title: 'Proposta', color: 'amber' },
    { id: 'fechado', title: 'Fechado', color: 'violet' }
];

const KANBAN_COLOR_OPTIONS = [
    { value: 'emerald', label: 'Verde' },
    { value: 'blue', label: 'Azul' },
    { value: 'amber', label: 'Amarelo' },
    { value: 'violet', label: 'Roxo' },
    { value: 'rose', label: 'Rosa' },
    { value: 'slate', label: 'Neutro' }
];

const getKanbanColorClasses = (color) => {
    const key = String(color || '').toLowerCase();
    const map = {
        emerald: {
            border: 'border-emerald-500/30',
            dot: 'bg-emerald-400',
            badge: 'bg-emerald-500/10 text-emerald-200 border-emerald-500/20',
            leftBorder: 'border-l-emerald-500/60'
        },
        blue: {
            border: 'border-blue-500/30',
            dot: 'bg-blue-400',
            badge: 'bg-blue-500/10 text-blue-200 border-blue-500/20',
            leftBorder: 'border-l-blue-500/60'
        },
        amber: {
            border: 'border-amber-500/30',
            dot: 'bg-amber-400',
            badge: 'bg-amber-500/10 text-amber-200 border-amber-500/20',
            leftBorder: 'border-l-amber-500/60'
        },
        violet: {
            border: 'border-violet-500/30',
            dot: 'bg-violet-400',
            badge: 'bg-violet-500/10 text-violet-200 border-violet-500/20',
            leftBorder: 'border-l-violet-500/60'
        },
        rose: {
            border: 'border-rose-500/30',
            dot: 'bg-rose-400',
            badge: 'bg-rose-500/10 text-rose-200 border-rose-500/20',
            leftBorder: 'border-l-rose-500/60'
        },
        slate: {
            border: 'border-white/15',
            dot: 'bg-white/40',
            badge: 'bg-white/5 text-white/70 border-white/10',
            leftBorder: 'border-l-white/20'
        }
    };
    return map[key] || map.slate;
};

const makeId = () => `col_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

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
    const [saving, setSaving] = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    const [viewMode, setViewMode] = useState('list');
    const [kanbanColumns, setKanbanColumns] = useState([]);
    const [showKanbanSettings, setShowKanbanSettings] = useState(false);
    const [draftKanbanColumns, setDraftKanbanColumns] = useState([]);
    const [newKanbanColumnTitle, setNewKanbanColumnTitle] = useState('');
    const [newKanbanColumnColor, setNewKanbanColumnColor] = useState('emerald');
    const [kanbanContacts, setKanbanContacts] = useState([]);
    const [kanbanLoading, setKanbanLoading] = useState(false);
    const [dragOverColumnId, setDragOverColumnId] = useState(null);

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

    const kanbanStorageKey = tenantId ? `contacts-kanban:${tenantId}` : 'contacts-kanban:no-tenant';

    const normalizeColumns = useCallback((input) => {
        const cols = Array.isArray(input) ? input : [];
        const normalized = cols
            .map((c) => ({
                id: String(c?.id || '').trim(),
                title: String(c?.title || '').trim(),
                color: String(c?.color || 'slate').trim()
            }))
            .filter((c) => c.id && c.id !== KANBAN_UNASSIGNED_COLUMN_ID && c.title);
        if (normalized.length === 0) return DEFAULT_KANBAN_COLUMNS;
        const seen = new Set();
        const dedup = [];
        for (const c of normalized) {
            if (seen.has(c.id)) continue;
            seen.add(c.id);
            dedup.push(c);
        }
        return dedup;
    }, []);

    const loadKanbanConfig = useCallback(() => {
        try {
            const raw = localStorage.getItem(kanbanStorageKey);
            if (!raw) return normalizeColumns(DEFAULT_KANBAN_COLUMNS);
            const parsed = JSON.parse(raw);
            return normalizeColumns(parsed?.columns);
        } catch {
            return normalizeColumns(DEFAULT_KANBAN_COLUMNS);
        }
    }, [kanbanStorageKey, normalizeColumns]);

    const saveKanbanConfig = useCallback((columns) => {
        try {
            localStorage.setItem(kanbanStorageKey, JSON.stringify({ columns }));
        } catch {
            null;
        }
    }, [kanbanStorageKey]);

    const allColumnsForBoard = [
        { id: KANBAN_UNASSIGNED_COLUMN_ID, title: 'Sem Coluna', color: 'slate', fixed: true },
        ...(kanbanColumns || [])
    ];

    const isKnownColumnId = useCallback((columnId) => {
        const id = String(columnId || '');
        return allColumnsForBoard.some((c) => c.id === id);
    }, [allColumnsForBoard]);

    const getContactColumnId = useCallback((contact) => {
        const raw = contact?.customFields?.[KANBAN_CUSTOM_FIELD_KEY];
        const desired = String(raw || '').trim();
        if (desired && isKnownColumnId(desired)) return desired;
        return KANBAN_UNASSIGNED_COLUMN_ID;
    }, [isKnownColumnId]);

    const loadKanbanContacts = useCallback(async (search = '') => {
        if (!tenantId) {
            setKanbanContacts([]);
            toast.error('Tenant não identificado');
            return;
        }

        setKanbanLoading(true);
        try {
            const pageLimit = 200;
            let pageOffset = 0;
            let totalCount = Infinity;
            const all = [];

            while (all.length < totalCount) {
                const data = await ContactsAPI.list(tenantId, search, pageLimit, pageOffset);
                const batch = data?.contacts || [];
                const reportedTotal = typeof data?.total === 'number' ? data.total : null;
                if (typeof reportedTotal === 'number') totalCount = reportedTotal;

                all.push(...batch);
                if (batch.length === 0) break;
                pageOffset += pageLimit;
                if (pageOffset > 20000) break;
            }

            setKanbanContacts(all);
        } catch (error) {
            console.error('Error loading kanban contacts:', error);
            toast.error('Erro ao carregar contatos');
            setKanbanContacts([]);
        } finally {
            setKanbanLoading(false);
        }
    }, [tenantId]);

    const moveContactToColumn = useCallback(async (contactId, toColumnId) => {
        const id = String(contactId || '');
        const toId = String(toColumnId || '');
        if (!id || !toId) return;

        const target = (kanbanContacts || []).find((c) => String(c?.id || '') === id);
        if (!target) return;

        const fromId = getContactColumnId(target);
        if (fromId === toId) return;

        const prevCustomFields = target?.customFields || {};
        const nextCustomFields = { ...prevCustomFields, [KANBAN_CUSTOM_FIELD_KEY]: toId };

        setKanbanContacts((prev) =>
            (prev || []).map((c) =>
                String(c?.id || '') === id
                    ? { ...c, customFields: nextCustomFields }
                    : c
            )
        );
        setContacts((prev) =>
            (prev || []).map((c) =>
                String(c?.id || '') === id
                    ? { ...c, customFields: nextCustomFields }
                    : c
            )
        );

        try {
            await ContactsAPI.update(id, { custom_fields: nextCustomFields });
        } catch (error) {
            setKanbanContacts((prev) =>
                (prev || []).map((c) =>
                    String(c?.id || '') === id
                        ? { ...c, customFields: prevCustomFields }
                        : c
                )
            );
            setContacts((prev) =>
                (prev || []).map((c) =>
                    String(c?.id || '') === id
                        ? { ...c, customFields: prevCustomFields }
                        : c
                )
            );
            toast.error(error?.message || 'Erro ao mover contato');
        }
    }, [getContactColumnId, kanbanContacts]);

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
        if (viewMode === 'kanban') {
            const cols = loadKanbanConfig();
            setKanbanColumns(cols);
            loadKanbanContacts(searchQuery);
        } else {
            loadContacts(searchQuery, 0);
        }
    }, [loadContacts, loadKanbanConfig, loadKanbanContacts, searchQuery, viewMode]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            if (viewMode === 'kanban') {
                loadKanbanContacts(searchQuery);
            } else {
                loadContacts(searchQuery, 0);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, loadContacts, loadKanbanContacts, viewMode]);

    useEffect(() => {
        if (!showKanbanSettings) return;
        setDraftKanbanColumns(kanbanColumns);
        setNewKanbanColumnTitle('');
        setNewKanbanColumnColor('emerald');
    }, [showKanbanSettings, kanbanColumns]);

    const applyKanbanSettings = () => {
        const next = normalizeColumns(draftKanbanColumns);
        setKanbanColumns(next);
        saveKanbanConfig(next);
        setShowKanbanSettings(false);
    };

    const resetKanbanSettings = () => {
        const next = normalizeColumns(DEFAULT_KANBAN_COLUMNS);
        setDraftKanbanColumns(next);
    };

    const addKanbanColumn = () => {
        const title = String(newKanbanColumnTitle || '').trim();
        if (!title) {
            toast.error('Nome da coluna é obrigatório');
            return;
        }
        const next = [
            ...(draftKanbanColumns || []),
            { id: makeId(), title, color: newKanbanColumnColor || 'slate' }
        ];
        setDraftKanbanColumns(next);
        setNewKanbanColumnTitle('');
        setNewKanbanColumnColor('emerald');
    };

    const updateDraftColumn = (id, patch) => {
        setDraftKanbanColumns((prev) =>
            (prev || []).map((c) => (c.id === id ? { ...c, ...patch } : c))
        );
    };

    const moveDraftColumn = (id, direction) => {
        setDraftKanbanColumns((prev) => {
            const cols = [...(prev || [])];
            const idx = cols.findIndex((c) => c.id === id);
            if (idx < 0) return cols;
            const nextIdx = direction === 'up' ? idx - 1 : idx + 1;
            if (nextIdx < 0 || nextIdx >= cols.length) return cols;
            const swap = cols[nextIdx];
            cols[nextIdx] = cols[idx];
            cols[idx] = swap;
            return cols;
        });
    };

    const removeDraftColumn = (id) => {
        setDraftKanbanColumns((prev) => (prev || []).filter((c) => c.id !== id));
    };

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

            await ContactsAPI.create(tenantId, {
                name: formName.trim(),
                phone: formPhone.trim(),
                email: formEmail.trim() || null,
                tags,
                custom_fields: customFields
            });

            toast.success('Contato criado com sucesso!');
            setShowCreateModal(false);
            if (viewMode === 'kanban') {
                loadKanbanContacts(searchQuery);
            } else {
                loadContacts(searchQuery, offset);
            }
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
            if (viewMode === 'kanban') {
                loadKanbanContacts(searchQuery);
            } else {
                loadContacts(searchQuery, offset);
            }
        } catch (error) {
            if (error.response?.status === 404) {
                toast.error('Contato não encontrado. Ele pode ter sido excluído.');
                setShowEditModal(false);
                if (viewMode === 'kanban') {
                    loadKanbanContacts(searchQuery);
                } else {
                    loadContacts(searchQuery, offset);
                }
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

            if (viewMode === 'kanban') {
                setKanbanContacts((prev) => (prev || []).filter((c) => String(c?.id || '') !== String(contactId)));
            } else {
                const isLastItemOnPage = (contacts || []).length === 1;
                const nextOffset = isLastItemOnPage ? Math.max(0, offset - limit) : offset;
                loadContacts(searchQuery, nextOffset);
            }
        } catch (error) {
            toast.error(error.message || 'Erro ao excluir contato');
        } finally {
            setDeletingId(null);
        }
    };

    const handleDeleteAllContacts = async () => {
        const currentTotal = viewMode === 'kanban' ? (kanbanContacts || []).length : total;
        if (currentTotal === 0) {
            toast.error('Não há contatos para excluir');
            return;
        }

        const ok = window.confirm(
            `Tem certeza que deseja excluir TODOS os ${currentTotal} contato(s)?\n\nEsta ação não pode ser desfeita!`
        );
        if (!ok) return;

        setLoading(true);
        try {
            const result = await ContactsAPI.purgeAll(tenantId);
            toast.success(`${result.deletedContacts || 0} contato(s) excluído(s) com sucesso!`);
            if (viewMode === 'kanban') {
                setKanbanContacts([]);
            } else {
                loadContacts(searchQuery, 0);
            }
        } catch (error) {
            toast.error(error.message || 'Erro ao excluir contatos');
        } finally {
            setLoading(false);
        }
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
    const headerTotal = viewMode === 'kanban' ? (kanbanContacts || []).length : total;

    return (
        <div className="h-full min-h-0 flex flex-col p-4 lg:p-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white">Contatos</h1>
                    <p className="text-white/60 text-sm mt-1">
                        {headerTotal} contato{headerTotal !== 1 ? 's' : ''} encontrado{headerTotal !== 1 ? 's' : ''}
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
                        <button
                            type="button"
                            onClick={() => setViewMode('kanban')}
                            aria-pressed={viewMode === 'kanban'}
                            className={cn(
                                'p-2 rounded-lg transition-colors',
                                viewMode === 'kanban'
                                    ? 'bg-white/10 text-white'
                                    : 'text-white/60 hover:bg-white/10 hover:text-white'
                            )}
                            title="Kanban"
                        >
                            <Columns3 className="w-4 h-4" />
                        </button>
                    </div>
                    {viewMode === 'kanban' && (
                        <GlassButton
                            onClick={() => setShowKanbanSettings(true)}
                            variant="secondary"
                            className="flex items-center gap-2"
                        >
                            <Settings className="w-4 h-4" />
                            Colunas
                        </GlassButton>
                    )}
                    <GlassButton
                        onClick={handleCreateContact}
                        className="flex items-center gap-2"
                    >
                        <Plus className="w-4 h-4" />
                        Novo Contato
                    </GlassButton>
                    {headerTotal > 0 && (
                        <GlassButton
                            onClick={handleDeleteAllContacts}
                            variant="secondary"
                            className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 border-red-500/20"
                        >
                            <Trash2 className="w-4 h-4" />
                            Excluir Todos
                        </GlassButton>
                    )}
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
                {viewMode === 'kanban' ? (
                    kanbanLoading ? (
                        <div className="flex items-center justify-center h-64">
                            <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin" />
                        </div>
                    ) : (kanbanContacts || []).length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-white/50">
                            <User className="w-16 h-16 mb-4 opacity-50" />
                            <p className="text-lg font-medium">Nenhum contato encontrado</p>
                            <p className="text-sm mt-1">Ajuste a busca ou crie um novo contato</p>
                        </div>
                    ) : (
                        <div className="h-full min-h-0">
                            <div className="h-full min-h-0 overflow-x-auto overflow-y-hidden">
                                <div className="min-h-full flex gap-4 pr-2">
                                    {allColumnsForBoard.map((col) => {
                                        const color = getKanbanColorClasses(col.color);
                                        const columnContacts = (kanbanContacts || []).filter((c) => getContactColumnId(c) === col.id);

                                        return (
                                            <div
                                                key={col.id}
                                                className={cn(
                                                    'w-[320px] min-w-[320px] h-full min-h-0 flex flex-col rounded-2xl border bg-white/5 backdrop-blur-sm',
                                                    color.border,
                                                    dragOverColumnId === col.id ? 'ring-2 ring-emerald-500/30' : 'ring-0'
                                                )}
                                                onDragOver={(e) => {
                                                    e.preventDefault();
                                                    e.dataTransfer.dropEffect = 'move';
                                                    setDragOverColumnId(col.id);
                                                }}
                                                onDragLeave={() => {
                                                    setDragOverColumnId((prev) => (prev === col.id ? null : prev));
                                                }}
                                                onDrop={(e) => {
                                                    e.preventDefault();
                                                    const droppedId = String(e.dataTransfer.getData('text/plain') || '').trim();
                                                    setDragOverColumnId(null);
                                                    if (!droppedId) return;
                                                    moveContactToColumn(droppedId, col.id);
                                                }}
                                            >
                                                <div className="px-4 py-3 border-b border-white/10">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <span className={cn('w-2 h-2 rounded-full', color.dot)} />
                                                            <h3 className="text-sm font-semibold text-white truncate">
                                                                {col.title}
                                                            </h3>
                                                        </div>
                                                        <span className={cn('text-xs px-2 py-0.5 rounded-lg border', color.badge)}>
                                                            {columnContacts.length}
                                                        </span>
                                                    </div>
                                                </div>

                                                <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
                                                    {columnContacts.map((contact) => (
                                                        <div
                                                            key={contact.id}
                                                            draggable
                                                            onDragStart={(e) => {
                                                                e.dataTransfer.setData('text/plain', String(contact.id));
                                                                e.dataTransfer.effectAllowed = 'move';
                                                            }}
                                                            onClick={() => handleEditContact(contact)}
                                                            className={cn(
                                                                'rounded-xl border bg-white/5 hover:bg-white/10 transition-colors cursor-pointer p-3 select-none',
                                                                'border-white/10 border-l-2',
                                                                color.leftBorder
                                                            )}
                                                        >
                                                            <div className="flex items-start justify-between gap-3">
                                                                <div className="flex items-center gap-3 min-w-0">
                                                                    <ContactAvatar name={contact.name} className="w-9 h-9 text-sm" />
                                                                    <div className="min-w-0">
                                                                        <p className="text-sm font-semibold text-white truncate">
                                                                            {contact.name || 'Sem nome'}
                                                                        </p>
                                                                        <p className="text-xs text-white/50 truncate">
                                                                            {contact.phone || 'Sem telefone'}
                                                                        </p>
                                                                    </div>
                                                                </div>
                                                                <button
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        handleViewInInbox(contact);
                                                                    }}
                                                                    className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors shrink-0"
                                                                    title="Ver conversas"
                                                                >
                                                                    <MessageSquare className="w-4 h-4" />
                                                                </button>
                                                            </div>

                                                            {(contact.tags || []).length > 0 && (
                                                                <div className="mt-3 flex flex-wrap gap-1">
                                                                    {(contact.tags || []).slice(0, 3).map((tag, idx) => (
                                                                        <span
                                                                            key={`${contact.id}-${idx}`}
                                                                            className="px-2 py-0.5 rounded-md text-[11px] bg-white/5 text-white/70 border border-white/10"
                                                                        >
                                                                            {tag}
                                                                        </span>
                                                                    ))}
                                                                    {(contact.tags || []).length > 3 && (
                                                                        <span className="text-[11px] text-white/40">
                                                                            +{(contact.tags || []).length - 3}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            )}

                                                            {(contact.firstContactAt || contact.createdAt) && (
                                                                <div className="mt-3 text-[11px] text-white/40">
                                                                    1º contato {formatDate(contact.firstContactAt || contact.createdAt)}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )
                ) : loading ? (
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
                                                    {contact.source && (
                                                        <span className="px-2 py-0.5 rounded text-xs bg-white/10 text-white/60">
                                                            {contact.source}
                                                        </span>
                                                    )}
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
            {viewMode !== 'kanban' && totalPages > 1 && (
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
                <DialogContent className="max-w-lg" aria-describedby={undefined}>
                    <VisuallyHidden.Root>
                        <DialogTitle>Novo Contato</DialogTitle>
                    </VisuallyHidden.Root>
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
                <DialogContent className="max-w-lg" aria-describedby={undefined}>
                    <VisuallyHidden.Root>
                        <DialogTitle>Editar Contato</DialogTitle>
                    </VisuallyHidden.Root>
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

            <Dialog open={showKanbanSettings} onOpenChange={setShowKanbanSettings}>
                <DialogContent className="max-w-2xl" aria-describedby={undefined}>
                    <VisuallyHidden.Root>
                        <DialogTitle>Colunas do Kanban</DialogTitle>
                        <DialogDescription>Configuração das colunas usadas no Kanban de contatos.</DialogDescription>
                    </VisuallyHidden.Root>
                    <div className="p-6">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <Columns3 className="w-5 h-5 text-emerald-400" />
                                Colunas do Kanban
                            </h2>
                            <button
                                onClick={() => setShowKanbanSettings(false)}
                                className="p-2 rounded-lg hover:bg-white/10 text-white/60"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="space-y-5">
                            <div className="space-y-3">
                                {(draftKanbanColumns || []).length === 0 ? (
                                    <div className="text-sm text-white/50">
                                        Nenhuma coluna configurada.
                                    </div>
                                ) : (
                                    (draftKanbanColumns || []).map((col, index) => (
                                        <div
                                            key={col.id}
                                            className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-xl border border-white/10 bg-white/5"
                                        >
                                            <div className="flex-1 min-w-0">
                                                <label className="block text-xs font-medium text-white/60 mb-1">
                                                    Nome
                                                </label>
                                                <GlassInput
                                                    value={col.title}
                                                    onChange={(e) => updateDraftColumn(col.id, { title: e.target.value })}
                                                    placeholder="Nome da coluna"
                                                />
                                            </div>
                                            <div className="sm:w-56">
                                                <label className="block text-xs font-medium text-white/60 mb-1">
                                                    Cor
                                                </label>
                                                <select
                                                    value={col.color || 'slate'}
                                                    onChange={(e) => updateDraftColumn(col.id, { color: e.target.value })}
                                                    className="w-full px-3 py-2.5 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                                >
                                                    {KANBAN_COLOR_OPTIONS.map((opt) => (
                                                        <option key={opt.value} value={opt.value} className="bg-emerald-900">
                                                            {opt.label}
                                                        </option>
                                                    ))}
                                                </select>
                                            </div>
                                            <div className="flex items-center gap-2 sm:pt-6 shrink-0">
                                                <button
                                                    type="button"
                                                    onClick={() => moveDraftColumn(col.id, 'up')}
                                                    disabled={index === 0}
                                                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                    title="Mover para cima"
                                                >
                                                    <ArrowUp className="w-4 h-4" />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => moveDraftColumn(col.id, 'down')}
                                                    disabled={index === (draftKanbanColumns || []).length - 1}
                                                    className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                                    title="Mover para baixo"
                                                >
                                                    <ArrowDown className="w-4 h-4" />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => removeDraftColumn(col.id)}
                                                    className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-300 hover:text-red-200 transition-colors"
                                                    title="Remover coluna"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>

                            <div className="p-4 rounded-xl border border-white/10 bg-white/5">
                                <div className="flex items-center justify-between gap-3 mb-3">
                                    <div className="text-sm font-semibold text-white">Adicionar coluna</div>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs font-medium text-white/60 mb-1">
                                            Nome
                                        </label>
                                        <GlassInput
                                            value={newKanbanColumnTitle}
                                            onChange={(e) => setNewKanbanColumnTitle(e.target.value)}
                                            placeholder="Ex: Em atendimento"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-medium text-white/60 mb-1">
                                            Cor
                                        </label>
                                        <select
                                            value={newKanbanColumnColor}
                                            onChange={(e) => setNewKanbanColumnColor(e.target.value)}
                                            className="w-full px-3 py-2.5 bg-white/10 border border-white/20 rounded-xl text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                                        >
                                            {KANBAN_COLOR_OPTIONS.map((opt) => (
                                                <option key={opt.value} value={opt.value} className="bg-emerald-900">
                                                    {opt.label}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                                <div className="flex justify-end mt-3">
                                    <GlassButton onClick={addKanbanColumn} className="flex items-center gap-2">
                                        <Plus className="w-4 h-4" />
                                        Adicionar
                                    </GlassButton>
                                </div>
                            </div>

                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pt-2">
                                <GlassButton variant="secondary" onClick={resetKanbanSettings}>
                                    Restaurar padrão
                                </GlassButton>
                                <div className="flex justify-end gap-3">
                                    <GlassButton variant="secondary" onClick={() => setShowKanbanSettings(false)}>
                                        Cancelar
                                    </GlassButton>
                                    <GlassButton onClick={applyKanbanSettings}>
                                        Salvar
                                    </GlassButton>
                                </div>
                            </div>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default Contacts;
