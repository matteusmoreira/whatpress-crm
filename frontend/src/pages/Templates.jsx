import React, { useState, useEffect, useCallback } from 'react';
import {
    FileText,
    Plus,
    Edit2,
    Trash2,
    Copy,
    Tag,
    Search,
    X,
    Check,
    Image,
    Video,
    File
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { TemplatesAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const CATEGORIES = [
    { id: 'general', label: 'Geral', color: 'gray' },
    { id: 'marketing', label: 'Marketing', color: 'purple' },
    { id: 'support', label: 'Suporte', color: 'blue' },
    { id: 'sales', label: 'Vendas', color: 'emerald' }
];

// Template Card
const TemplateCard = ({ template, onEdit, onDelete, onCopy }) => {
    const category = CATEGORIES.find(c => c.id === template.category) || CATEGORIES[0];
    const badgeVariantByCategory = {
        general: 'neutral',
        marketing: 'purple',
        support: 'info',
        sales: 'success'
    };

    const getMediaIcon = () => {
        switch (template.mediaType) {
            case 'image': return <Image className="w-4 h-4" />;
            case 'video': return <Video className="w-4 h-4" />;
            case 'document': return <File className="w-4 h-4" />;
            default: return null;
        }
    };

    return (
        <div className="p-4 bg-white/5 hover:bg-white/10 rounded-xl border border-white/10 transition-colors group">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                    <FileText className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-white font-medium">{template.name}</h3>
                </div>
                <GlassBadge
                    variant={badgeVariantByCategory[category.id] || 'neutral'}
                    className="text-xs px-2 py-0.5"
                >
                    {category.label}
                </GlassBadge>
            </div>

            <div className="p-3 bg-black/20 rounded-lg mb-3">
                <p className="text-white/70 text-sm whitespace-pre-wrap line-clamp-3">{template.content}</p>
            </div>

            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-white/40 text-xs">
                    {template.mediaType && (
                        <span className="flex items-center gap-1">
                            {getMediaIcon()}
                            {template.mediaType}
                        </span>
                    )}
                    {template.variables?.length > 0 && (
                        <span className="flex items-center gap-1">
                            <Tag className="w-3 h-3" />
                            {template.variables.length} vars
                        </span>
                    )}
                    <span>Usado {template.usageCount || 0}x</span>
                </div>

                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={() => onCopy(template.content)}
                        className="p-1.5 text-white/40 hover:text-white hover:bg-white/10 rounded"
                        title="Copiar"
                    >
                        <Copy className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => onEdit(template)}
                        className="p-1.5 text-white/40 hover:text-white hover:bg-white/10 rounded"
                        title="Editar"
                    >
                        <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => onDelete(template.id)}
                        className="p-1.5 text-white/40 hover:text-red-400 hover:bg-red-500/20 rounded"
                        title="Excluir"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
};

// Template Form Modal
const TemplateFormModal = ({ isOpen, onClose, onSave, editingTemplate }) => {
    const [formData, setFormData] = useState({
        name: '',
        category: 'general',
        content: '',
        variables: [],
        mediaUrl: '',
        mediaType: ''
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (editingTemplate) {
            setFormData({
                name: editingTemplate.name,
                category: editingTemplate.category,
                content: editingTemplate.content,
                variables: editingTemplate.variables || [],
                mediaUrl: editingTemplate.mediaUrl || '',
                mediaType: editingTemplate.mediaType || ''
            });
        } else {
            setFormData({
                name: '',
                category: 'general',
                content: '',
                variables: [],
                mediaUrl: '',
                mediaType: ''
            });
        }
    }, [editingTemplate, isOpen]);

    // Extract variables from content
    const extractVariables = (content) => {
        const matches = content.match(/\{\{(\w+)\}\}/g) || [];
        return matches.map(m => ({
            name: m.replace(/\{\{|\}\}/g, ''),
            placeholder: m
        }));
    };

    const handleContentChange = (content) => {
        const variables = extractVariables(content);
        setFormData({ ...formData, content, variables });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.name.trim() || !formData.content.trim()) {
            toast.error('Preencha nome e conteúdo');
            return;
        }

        setSaving(true);
        try {
            await onSave(formData, editingTemplate?.id);
            onClose();
        } catch (error) {
            toast.error('Erro ao salvar template');
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-lg bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl max-h-[90vh] overflow-hidden">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-emerald-400" />
                        <h2 className="text-lg font-semibold text-white">
                            {editingTemplate ? 'Editar Template' : 'Novo Template'}
                        </h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4 overflow-y-auto max-h-[70vh]">
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Nome *</label>
                        <GlassInput
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Ex: Boas-vindas padrão"
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Categoria</label>
                        <div className="grid grid-cols-4 gap-2">
                            {CATEGORIES.map(cat => (
                                <button
                                    key={cat.id}
                                    type="button"
                                    onClick={() => setFormData({ ...formData, category: cat.id })}
                                    className={cn(
                                        'px-3 py-2 rounded-lg text-sm transition-all',
                                        formData.category === cat.id
                                            ? 'bg-emerald-500/30 border-emerald-500 text-white'
                                            : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10'
                                    )}
                                    style={{ borderWidth: '1px' }}
                                >
                                    {cat.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">
                            Conteúdo *
                            <span className="text-white/40 ml-2">(Use {'{{variavel}}'} para variáveis)</span>
                        </label>
                        <textarea
                            value={formData.content}
                            onChange={(e) => handleContentChange(e.target.value)}
                            placeholder="Olá {{nome}}, como posso ajudar?"
                            rows={5}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                        />
                    </div>

                    {formData.variables.length > 0 && (
                        <div className="p-3 bg-white/5 rounded-lg">
                            <p className="text-white/50 text-xs mb-2">Variáveis detectadas:</p>
                            <div className="flex flex-wrap gap-2">
                                {formData.variables.map(v => (
                                    <GlassBadge key={v.name} variant="success" className="px-2 py-1 text-xs">
                                        {v.placeholder}
                                    </GlassBadge>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-white/70 text-sm mb-2 block">Tipo de Mídia</label>
                            <select
                                value={formData.mediaType}
                                onChange={(e) => setFormData({ ...formData, mediaType: e.target.value })}
                                className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                            >
                                <option value="">Nenhuma</option>
                                <option value="image">Imagem</option>
                                <option value="video">Vídeo</option>
                                <option value="document">Documento</option>
                            </select>
                        </div>
                        {formData.mediaType && (
                            <div>
                                <label className="text-white/70 text-sm mb-2 block">URL da Mídia</label>
                                <GlassInput
                                    type="url"
                                    value={formData.mediaUrl}
                                    onChange={(e) => setFormData({ ...formData, mediaUrl: e.target.value })}
                                    placeholder="https://..."
                                />
                            </div>
                        )}
                    </div>

                    <div className="flex gap-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 px-4 py-3 text-white/60 hover:text-white transition-colors"
                        >
                            Cancelar
                        </button>
                        <GlassButton type="submit" disabled={saving} className="flex-1">
                            <Check className="w-4 h-4 mr-2" />
                            {saving ? 'Salvando...' : editingTemplate ? 'Atualizar' : 'Criar'}
                        </GlassButton>
                    </div>
                </form>
            </div>
        </div>
    );
};

const Templates = () => {
    const { user } = useAuthStore();
    const [loading, setLoading] = useState(true);
    const [templates, setTemplates] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('all');
    const [showForm, setShowForm] = useState(false);
    const [editingTemplate, setEditingTemplate] = useState(null);

    const tenantId = user?.tenantId || 'tenant-1';

    const loadTemplates = useCallback(async () => {
        try {
            setLoading(true);
            const data = await TemplatesAPI.list(tenantId);
            setTemplates(data);
        } catch (error) {
            console.error('Error loading templates:', error);
            toast.error('Erro ao carregar templates');
        } finally {
            setLoading(false);
        }
    }, [tenantId]);

    useEffect(() => {
        loadTemplates();
    }, [loadTemplates]);

    const handleSave = async (formData, editId) => {
        if (editId) {
            await TemplatesAPI.update(editId, formData);
            toast.success('Template atualizado');
        } else {
            await TemplatesAPI.create(tenantId, formData);
            toast.success('Template criado');
        }
        loadTemplates();
    };

    const handleEdit = (template) => {
        setEditingTemplate(template);
        setShowForm(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Deseja excluir este template?')) return;

        try {
            await TemplatesAPI.delete(id);
            toast.success('Template excluído');
            loadTemplates();
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    const handleCopy = (content) => {
        navigator.clipboard.writeText(content);
        toast.success('Copiado para área de transferência');
    };

    const closeForm = () => {
        setShowForm(false);
        setEditingTemplate(null);
    };

    const filteredTemplates = templates.filter(t => {
        const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            t.content.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesCategory = selectedCategory === 'all' || t.category === selectedCategory;
        return matchesSearch && matchesCategory;
    });

    return (
        <div className="p-4 sm:p-5 lg:p-6 overflow-y-auto h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6 pl-16 lg:pl-0">
                <div>
                    <h1 className="wa-page-title flex items-center gap-2">
                        <FileText className="w-8 h-8 text-emerald-400" />
                        Templates
                    </h1>
                    <p className="wa-page-subtitle">Modelos de mensagem reutilizáveis</p>
                </div>
                <GlassButton onClick={() => setShowForm(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Novo Template
                </GlassButton>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-4 mb-6">
                <div className="relative flex-1 min-w-[200px]">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <GlassInput
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Buscar templates..."
                        className="pl-10"
                    />
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setSelectedCategory('all')}
                        className={cn(
                            'px-4 py-2 rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                            selectedCategory === 'all'
                                ? 'bg-white/20 text-white'
                                : 'bg-white/5 text-white/60 hover:bg-white/10'
                        )}
                    >
                        Todos
                    </button>
                    {CATEGORIES.map(cat => (
                        <button
                            key={cat.id}
                            onClick={() => setSelectedCategory(cat.id)}
                            className={cn(
                                'px-4 py-2 rounded-lg text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                                selectedCategory === cat.id
                                    ? 'bg-white/20 text-white'
                                    : 'bg-white/5 text-white/60 hover:bg-white/10'
                            )}
                        >
                            {cat.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : filteredTemplates.length === 0 ? (
                <GlassCard className="p-12 text-center">
                    <FileText className="w-16 h-16 text-white/20 mx-auto mb-4" />
                    <h3 className="text-xl font-medium text-white mb-2">
                        {searchQuery || selectedCategory !== 'all' ? 'Nenhum template encontrado' : 'Nenhum template'}
                    </h3>
                    <p className="text-white/50 mb-6">
                        Crie templates para agilizar suas respostas.
                    </p>
                    {!searchQuery && selectedCategory === 'all' && (
                        <GlassButton onClick={() => setShowForm(true)}>
                            <Plus className="w-4 h-4 mr-2" />
                            Criar primeiro template
                        </GlassButton>
                    )}
                </GlassCard>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filteredTemplates.map(template => (
                        <TemplateCard
                            key={template.id}
                            template={template}
                            onEdit={handleEdit}
                            onDelete={handleDelete}
                            onCopy={handleCopy}
                        />
                    ))}
                </div>
            )}

            {/* Form Modal */}
            <TemplateFormModal
                isOpen={showForm}
                onClose={closeForm}
                onSave={handleSave}
                editingTemplate={editingTemplate}
            />
        </div>
    );
};

export default Templates;
