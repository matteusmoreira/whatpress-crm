import React, { useState, useEffect, useCallback } from 'react';
import {
    BookOpen,
    Plus,
    Edit2,
    Trash2,
    Search,
    X,
    Check,
    Eye,
    ThumbsUp,
    ThumbsDown,
    FolderOpen,
    FileText,
    HelpCircle,
    ChevronRight,
    Tag
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { KnowledgeBaseAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

// Tabs
const TABS = [
    { id: 'articles', label: 'Artigos', icon: FileText },
    { id: 'faqs', label: 'FAQs', icon: HelpCircle },
    { id: 'categories', label: 'Categorias', icon: FolderOpen }
];

// Article Card
const ArticleCard = ({ article, onEdit, onDelete, onView }) => {
    return (
        <div
            className="p-4 bg-white/5 hover:bg-white/10 rounded-xl border border-white/10 transition-colors cursor-pointer group"
            onClick={() => onView(article)}
        >
            <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        {article.isFeatured && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400">
                                Destaque
                            </span>
                        )}
                        {!article.isPublished && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-500/20 text-gray-400">
                                Rascunho
                            </span>
                        )}
                    </div>
                    <h3 className="text-white font-medium">{article.title}</h3>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={(e) => { e.stopPropagation(); onEdit(article); }}
                        className="p-1.5 text-white/40 hover:text-white hover:bg-white/10 rounded"
                    >
                        <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete(article.id); }}
                        className="p-1.5 text-white/40 hover:text-red-400 hover:bg-red-500/20 rounded"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {article.excerpt && (
                <p className="text-white/50 text-sm line-clamp-2 mb-3">{article.excerpt}</p>
            )}

            <div className="flex items-center gap-4 text-xs text-white/40">
                <span className="flex items-center gap-1">
                    <Eye className="w-3 h-3" />
                    {article.views || 0}
                </span>
                <span className="flex items-center gap-1">
                    <ThumbsUp className="w-3 h-3" />
                    {article.helpfulYes || 0}
                </span>
                {article.category && (
                    <span className="flex items-center gap-1">
                        <FolderOpen className="w-3 h-3" />
                        {article.category.name}
                    </span>
                )}
            </div>
        </div>
    );
};

// FAQ Item
const FaqItem = ({ faq, onDelete }) => {
    const [expanded, setExpanded] = useState(false);

    return (
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <HelpCircle className="w-5 h-5 text-emerald-400 flex-shrink-0" />
                    <span className="text-white">{faq.question}</span>
                </div>
                <ChevronRight className={cn(
                    'w-5 h-5 text-white/40 transition-transform',
                    expanded && 'rotate-90'
                )} />
            </button>

            {expanded && (
                <div className="px-4 pb-4 border-t border-white/10">
                    <div className="pt-4">
                        <p className="text-white/70 whitespace-pre-wrap">{faq.answer}</p>
                        <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/10">
                            <span className="text-xs text-white/40">
                                Usado {faq.usageCount || 0}x
                            </span>
                            <button
                                onClick={() => onDelete(faq.id)}
                                className="text-xs text-red-400 hover:underline"
                            >
                                Excluir
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// Article Form Modal
const ArticleFormModal = ({ isOpen, onClose, onSave, editingArticle, categories }) => {
    const [formData, setFormData] = useState({
        title: '',
        content: '',
        excerpt: '',
        categoryId: '',
        keywords: [],
        isPublished: false,
        isFeatured: false
    });
    const [keywordInput, setKeywordInput] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (editingArticle) {
            setFormData({
                title: editingArticle.title,
                content: editingArticle.content,
                excerpt: editingArticle.excerpt || '',
                categoryId: editingArticle.category?.id || '',
                keywords: editingArticle.keywords || [],
                isPublished: editingArticle.isPublished,
                isFeatured: editingArticle.isFeatured
            });
        } else {
            setFormData({
                title: '',
                content: '',
                excerpt: '',
                categoryId: '',
                keywords: [],
                isPublished: false,
                isFeatured: false
            });
        }
    }, [editingArticle, isOpen]);

    const addKeyword = () => {
        if (keywordInput.trim() && !formData.keywords.includes(keywordInput.trim())) {
            setFormData({ ...formData, keywords: [...formData.keywords, keywordInput.trim()] });
            setKeywordInput('');
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.title.trim() || !formData.content.trim()) {
            toast.error('Preencha título e conteúdo');
            return;
        }

        setSaving(true);
        try {
            await onSave({
                title: formData.title,
                content: formData.content,
                excerpt: formData.excerpt,
                category_id: formData.categoryId || null,
                keywords: formData.keywords,
                is_published: formData.isPublished,
                is_featured: formData.isFeatured
            }, editingArticle?.id);
            onClose();
        } catch (error) {
            toast.error('Erro ao salvar artigo');
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-2xl bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl max-h-[90vh] overflow-hidden">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <h2 className="text-lg font-semibold text-white">
                        {editingArticle ? 'Editar Artigo' : 'Novo Artigo'}
                    </h2>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4 overflow-y-auto max-h-[70vh]">
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Título *</label>
                        <GlassInput
                            type="text"
                            value={formData.title}
                            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                            placeholder="Como configurar..."
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Categoria</label>
                        <select
                            value={formData.categoryId}
                            onChange={(e) => setFormData({ ...formData, categoryId: e.target.value })}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                        >
                            <option value="">Sem categoria</option>
                            {categories.map(cat => (
                                <option key={cat.id} value={cat.id}>{cat.name}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Resumo</label>
                        <textarea
                            value={formData.excerpt}
                            onChange={(e) => setFormData({ ...formData, excerpt: e.target.value })}
                            placeholder="Breve descrição do artigo..."
                            rows={2}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Conteúdo *</label>
                        <textarea
                            value={formData.content}
                            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                            placeholder="Escreva o conteúdo do artigo..."
                            rows={8}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Palavras-chave</label>
                        <div className="flex gap-2">
                            <GlassInput
                                type="text"
                                value={keywordInput}
                                onChange={(e) => setKeywordInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword())}
                                placeholder="Adicionar palavra-chave..."
                                className="flex-1"
                            />
                            <GlassButton type="button" onClick={addKeyword}>Adicionar</GlassButton>
                        </div>
                        {formData.keywords.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-2">
                                {formData.keywords.map(kw => (
                                    <span key={kw} className="flex items-center gap-1 px-2 py-1 bg-emerald-500/20 text-emerald-400 rounded text-sm">
                                        <Tag className="w-3 h-3" />
                                        {kw}
                                        <button
                                            type="button"
                                            onClick={() => setFormData({ ...formData, keywords: formData.keywords.filter(k => k !== kw) })}
                                            className="ml-1 hover:text-white"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={formData.isPublished}
                                onChange={(e) => setFormData({ ...formData, isPublished: e.target.checked })}
                                className="w-4 h-4 rounded border-white/20 bg-white/10 text-emerald-500 focus:ring-emerald-500"
                            />
                            <span className="text-white/70 text-sm">Publicar</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={formData.isFeatured}
                                onChange={(e) => setFormData({ ...formData, isFeatured: e.target.checked })}
                                className="w-4 h-4 rounded border-white/20 bg-white/10 text-emerald-500 focus:ring-emerald-500"
                            />
                            <span className="text-white/70 text-sm">Destaque</span>
                        </label>
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
                            {saving ? 'Salvando...' : editingArticle ? 'Atualizar' : 'Criar'}
                        </GlassButton>
                    </div>
                </form>
            </div>
        </div>
    );
};

const KnowledgeBase = () => {
    const { user } = useAuthStore();
    const [activeTab, setActiveTab] = useState('articles');
    const [loading, setLoading] = useState(true);
    const [articles, setArticles] = useState([]);
    const [faqs, setFaqs] = useState([]);
    const [categories, setCategories] = useState([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState(null);
    const [showArticleForm, setShowArticleForm] = useState(false);
    const [editingArticle, setEditingArticle] = useState(null);

    const tenantId = user?.tenantId || 'tenant-1';

    const loadData = useCallback(async () => {
        try {
            setLoading(true);
            const [articlesData, faqsData, categoriesData] = await Promise.all([
                KnowledgeBaseAPI.listArticles(tenantId, null, false),
                KnowledgeBaseAPI.listFaqs(tenantId),
                KnowledgeBaseAPI.listCategories(tenantId)
            ]);
            setArticles(articlesData);
            setFaqs(faqsData);
            setCategories(categoriesData);
        } catch (error) {
            console.error('Error loading KB data:', error);
            toast.error('Erro ao carregar base de conhecimento');
        } finally {
            setLoading(false);
        }
    }, [tenantId]);

    useEffect(() => {
        loadData();
    }, [loadData]);

    const handleSearch = async () => {
        if (!searchQuery.trim()) {
            setSearchResults(null);
            return;
        }
        try {
            const results = await KnowledgeBaseAPI.search(tenantId, searchQuery);
            setSearchResults(results);
        } catch (error) {
            console.error('Search error:', error);
        }
    };

    const handleSaveArticle = async (formData, editId) => {
        if (editId) {
            await KnowledgeBaseAPI.updateArticle(editId, formData);
            toast.success('Artigo atualizado');
        } else {
            await KnowledgeBaseAPI.createArticle(tenantId, formData);
            toast.success('Artigo criado');
        }
        loadData();
    };

    const handleDeleteArticle = async (id) => {
        if (!window.confirm('Deseja excluir este artigo?')) return;
        try {
            await KnowledgeBaseAPI.deleteArticle(id);
            toast.success('Artigo excluído');
            loadData();
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    const handleDeleteFaq = async (id) => {
        if (!window.confirm('Deseja excluir esta FAQ?')) return;
        try {
            await KnowledgeBaseAPI.deleteFaq(id);
            toast.success('FAQ excluída');
            loadData();
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    const handleViewArticle = async (article) => {
        await KnowledgeBaseAPI.viewArticle(article.id);
        setEditingArticle(article);
        setShowArticleForm(true);
    };

    return (
        <div className="p-6 overflow-y-auto h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <BookOpen className="w-8 h-8 text-emerald-400" />
                        Base de Conhecimento
                    </h1>
                    <p className="text-white/50 mt-1">Artigos, FAQs e documentação</p>
                </div>
                {activeTab === 'articles' && (
                    <GlassButton onClick={() => { setEditingArticle(null); setShowArticleForm(true); }}>
                        <Plus className="w-4 h-4 mr-2" />
                        Novo Artigo
                    </GlassButton>
                )}
            </div>

            {/* Search */}
            <div className="relative mb-6">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <GlassInput
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="Buscar artigos e FAQs..."
                    className="pl-10"
                />
                {searchResults && (
                    <button
                        onClick={() => { setSearchQuery(''); setSearchResults(null); }}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white"
                    >
                        <X className="w-4 h-4" />
                    </button>
                )}
            </div>

            {/* Search Results */}
            {searchResults && (
                <GlassCard className="p-4 mb-6">
                    <h3 className="text-white font-medium mb-3">Resultados da busca</h3>
                    {searchResults.articles.length === 0 && searchResults.faqs.length === 0 ? (
                        <p className="text-white/50">Nenhum resultado encontrado</p>
                    ) : (
                        <div className="space-y-2">
                            {searchResults.articles.map(a => (
                                <div key={a.id} className="p-3 bg-white/5 rounded-lg flex items-center gap-3">
                                    <FileText className="w-4 h-4 text-emerald-400" />
                                    <span className="text-white">{a.title}</span>
                                </div>
                            ))}
                            {searchResults.faqs.map(f => (
                                <div key={f.id} className="p-3 bg-white/5 rounded-lg flex items-center gap-3">
                                    <HelpCircle className="w-4 h-4 text-blue-400" />
                                    <span className="text-white">{f.question}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </GlassCard>
            )}

            {/* Tabs */}
            <div className="flex gap-2 mb-6">
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors',
                            activeTab === tab.id
                                ? 'bg-emerald-500/20 text-emerald-400'
                                : 'bg-white/5 text-white/60 hover:bg-white/10'
                        )}
                    >
                        <tab.icon className="w-4 h-4" />
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : (
                <>
                    {activeTab === 'articles' && (
                        articles.length === 0 ? (
                            <GlassCard className="p-12 text-center">
                                <FileText className="w-16 h-16 text-white/20 mx-auto mb-4" />
                                <h3 className="text-xl font-medium text-white mb-2">Nenhum artigo</h3>
                                <p className="text-white/50 mb-6">Crie artigos para a sua base de conhecimento.</p>
                                <GlassButton onClick={() => setShowArticleForm(true)}>
                                    <Plus className="w-4 h-4 mr-2" />
                                    Criar primeiro artigo
                                </GlassButton>
                            </GlassCard>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {articles.map(article => (
                                    <ArticleCard
                                        key={article.id}
                                        article={article}
                                        onEdit={(a) => { setEditingArticle(a); setShowArticleForm(true); }}
                                        onDelete={handleDeleteArticle}
                                        onView={handleViewArticle}
                                    />
                                ))}
                            </div>
                        )
                    )}

                    {activeTab === 'faqs' && (
                        faqs.length === 0 ? (
                            <GlassCard className="p-12 text-center">
                                <HelpCircle className="w-16 h-16 text-white/20 mx-auto mb-4" />
                                <h3 className="text-xl font-medium text-white mb-2">Nenhuma FAQ</h3>
                                <p className="text-white/50">Perguntas frequentes aparecerão aqui.</p>
                            </GlassCard>
                        ) : (
                            <div className="space-y-3">
                                {faqs.map(faq => (
                                    <FaqItem key={faq.id} faq={faq} onDelete={handleDeleteFaq} />
                                ))}
                            </div>
                        )
                    )}

                    {activeTab === 'categories' && (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {categories.map(cat => (
                                <div key={cat.id} className="p-4 bg-white/5 rounded-xl border border-white/10">
                                    <div className="flex items-center gap-3 mb-2">
                                        <FolderOpen className="w-5 h-5 text-emerald-400" />
                                        <span className="text-white font-medium">{cat.name}</span>
                                    </div>
                                    {cat.description && (
                                        <p className="text-white/50 text-sm">{cat.description}</p>
                                    )}
                                </div>
                            ))}
                            {categories.length === 0 && (
                                <GlassCard className="col-span-full p-12 text-center">
                                    <FolderOpen className="w-16 h-16 text-white/20 mx-auto mb-4" />
                                    <h3 className="text-xl font-medium text-white mb-2">Nenhuma categoria</h3>
                                    <p className="text-white/50">Organize seus artigos em categorias.</p>
                                </GlassCard>
                            )}
                        </div>
                    )}
                </>
            )}

            {/* Article Form Modal */}
            <ArticleFormModal
                isOpen={showArticleForm}
                onClose={() => { setShowArticleForm(false); setEditingArticle(null); }}
                onSave={handleSaveArticle}
                editingArticle={editingArticle}
                categories={categories}
            />
        </div>
    );
};

export default KnowledgeBase;
