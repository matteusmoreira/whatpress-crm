import React, { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Zap, Clock, Tag, User, Plus, Edit2, Trash2, Check, X } from 'lucide-react';
import { GlassInput, GlassButton } from './GlassCard';
import { cn } from '../lib/utils';
import { QuickRepliesAPI } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { toast } from './ui/glass-toaster';

const CATEGORIES = [
  { id: 'all', label: 'Todas', icon: <MessageSquare className="w-4 h-4" /> },
  { id: 'greeting', label: 'Saudações', icon: <User className="w-4 h-4" /> },
  { id: 'support', label: 'Suporte', icon: <Zap className="w-4 h-4" /> },
  { id: 'info', label: 'Info', icon: <Clock className="w-4 h-4" /> },
  { id: 'closing', label: 'Fechamento', icon: <Tag className="w-4 h-4" /> },
  { id: 'custom', label: 'Personalizadas', icon: <MessageSquare className="w-4 h-4" /> }
];

const CATEGORY_ICONS = {
  greeting: '👋',
  support: '⚡',
  info: '📋',
  closing: '✅',
  sales: '💰',
  custom: '📝'
};

const QuickRepliesPanel = ({ onSelect, onClose }) => {
  const { user } = useAuthStore();
  const tenantId = user?.tenantId || 'tenant-1';

  const [replies, setReplies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({ title: '', content: '', category: 'custom' });
  const [saving, setSaving] = useState(false);

  const loadReplies = useCallback(async () => {
    try {
      setLoading(true);
      const data = await QuickRepliesAPI.list(tenantId);
      setReplies(data || []);
    } catch (error) {
      console.error('Error loading quick replies:', error);
      toast.error('Erro ao carregar respostas rápidas');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    loadReplies();
  }, [loadReplies]);

  const filteredReplies = replies.filter(reply => {
    const matchesCategory = selectedCategory === 'all' || reply.category === selectedCategory;
    const matchesSearch = (reply.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (reply.content || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleCreate = async () => {
    if (!formData.title.trim() || !formData.content.trim()) {
      toast.error('Preencha título e conteúdo');
      return;
    }

    try {
      setSaving(true);
      const newReply = await QuickRepliesAPI.create(tenantId, formData);
      setReplies([...replies, newReply]);
      setFormData({ title: '', content: '', category: 'custom' });
      setShowForm(false);
      toast.success('Resposta rápida criada');
    } catch (error) {
      toast.error('Erro ao criar resposta rápida');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!formData.title.trim() || !formData.content.trim()) {
      toast.error('Preencha título e conteúdo');
      return;
    }

    try {
      setSaving(true);
      const updated = await QuickRepliesAPI.update(editingId, formData);
      setReplies(replies.map(r => r.id === editingId ? { ...r, ...updated } : r));
      setFormData({ title: '', content: '', category: 'custom' });
      setEditingId(null);
      toast.success('Resposta rápida atualizada');
    } catch (error) {
      toast.error('Erro ao atualizar resposta rápida');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (replyId) => {
    const ok = window.confirm('Deseja excluir esta resposta rápida?');
    if (!ok) return;

    try {
      await QuickRepliesAPI.delete(replyId);
      setReplies(replies.filter(r => r.id !== replyId));
      toast.success('Resposta rápida excluída');
    } catch (error) {
      toast.error('Erro ao excluir resposta rápida');
    }
  };

  const startEdit = (reply) => {
    setEditingId(reply.id);
    setFormData({ title: reply.title, content: reply.content, category: reply.category || 'custom' });
    setShowForm(false);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setFormData({ title: '', content: '', category: 'custom' });
    setShowForm(false);
  };

  const getIcon = (category) => CATEGORY_ICONS[category] || '📝';

  return (
    <div className="absolute bottom-full left-0 right-0 mb-2 bg-emerald-900/98 border border-white/20 rounded-2xl shadow-2xl shadow-emerald-500/20 overflow-hidden z-[9999] pointer-events-auto">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Zap className="w-5 h-5 text-emerald-400" />
            Respostas Rápidas
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowForm(!showForm); setEditingId(null); setFormData({ title: '', content: '', category: 'custom' }); }}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-lg text-sm transition-colors",
                showForm ? "bg-emerald-500 text-white" : "bg-white/10 text-white/70 hover:bg-white/20 hover:text-white"
              )}
            >
              <Plus className="w-4 h-4" />
              Nova
            </button>
            <button
              onClick={onClose}
              className="text-white/40 hover:text-white transition-colors text-sm"
            >
              ESC
            </button>
          </div>
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Buscar resposta..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder:text-white/40 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          autoFocus={!showForm && !editingId}
        />

        {/* Categories */}
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all',
                selectedCategory === cat.id
                  ? 'bg-emerald-500 text-white'
                  : 'bg-white/10 text-white/70 hover:bg-white/20'
              )}
            >
              {cat.icon}
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* New/Edit Form */}
      {(showForm || editingId) && (
        <div className="p-4 border-b border-white/10 bg-white/5">
          <h4 className="text-white/80 text-sm font-medium mb-3">
            {editingId ? 'Editar Resposta' : 'Nova Resposta'}
          </h4>
          <div className="space-y-3">
            <GlassInput
              type="text"
              placeholder="Título (ex: Saudação)"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="text-sm"
              autoFocus
            />
            <textarea
              placeholder="Conteúdo da mensagem..."
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder:text-white/50 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50 min-h-[80px] resize-none"
            />
            <select
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            >
              <option value="greeting" className="bg-emerald-900">Saudações</option>
              <option value="support" className="bg-emerald-900">Suporte</option>
              <option value="info" className="bg-emerald-900">Informações</option>
              <option value="closing" className="bg-emerald-900">Fechamento</option>
              <option value="sales" className="bg-emerald-900">Vendas</option>
              <option value="custom" className="bg-emerald-900">Personalizadas</option>
            </select>
            <div className="flex gap-2">
              <GlassButton
                onClick={editingId ? handleUpdate : handleCreate}
                disabled={saving}
                className="flex-1 text-sm py-2"
              >
                <Check className="w-4 h-4 mr-1" />
                {editingId ? 'Salvar' : 'Criar'}
              </GlassButton>
              <button
                onClick={cancelEdit}
                className="px-4 py-2 text-sm text-white/60 hover:text-white transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Replies List */}
      <div className="max-h-64 overflow-y-auto p-2">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredReplies.length === 0 ? (
          <p className="text-white/50 text-center py-4">Nenhuma resposta encontrada</p>
        ) : (
          <div className="grid grid-cols-1 gap-2">
            {filteredReplies.map(reply => (
              <div
                key={reply.id}
                className="p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-all group"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{getIcon(reply.category)}</span>
                  <button
                    onClick={() => {
                      onSelect(reply.content);
                      onClose();
                    }}
                    className="flex-1 min-w-0 text-left"
                  >
                    <p className="text-white font-medium text-sm">{reply.title}</p>
                    <p className="text-white/60 text-sm truncate group-hover:text-white/80">
                      {reply.content}
                    </p>
                  </button>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => { e.stopPropagation(); startEdit(reply); }}
                      className="p-1.5 hover:bg-white/10 rounded-lg text-white/40 hover:text-white transition-colors"
                      title="Editar"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDelete(reply.id); }}
                      className="p-1.5 hover:bg-red-500/20 rounded-lg text-white/40 hover:text-red-400 transition-colors"
                      title="Excluir"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default QuickRepliesPanel;
