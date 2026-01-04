import React, { useState, useEffect, useCallback } from 'react';
import {
    Bot,
    MessageSquare,
    Clock,
    Zap,
    Plus,
    Edit2,
    Trash2,
    Power,
    PowerOff,
    X,
    Check,
    Send
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { AutoMessagesAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const MESSAGE_TYPES = [
    { id: 'welcome', label: 'Boas-vindas', icon: MessageSquare, color: 'emerald', description: 'Enviada quando um novo contato inicia uma conversa' },
    { id: 'away', label: 'Fora do Horário', icon: Clock, color: 'amber', description: 'Enviada fora do horário de atendimento' },
    { id: 'keyword', label: 'Palavra-chave', icon: Zap, color: 'purple', description: 'Enviada quando detectar uma palavra específica' }
];

const DAYS_OF_WEEK = [
    { id: 0, label: 'Dom' },
    { id: 1, label: 'Seg' },
    { id: 2, label: 'Ter' },
    { id: 3, label: 'Qua' },
    { id: 4, label: 'Qui' },
    { id: 5, label: 'Sex' },
    { id: 6, label: 'Sáb' }
];

// Auto Message Card Component
const AutoMessageCard = ({ message, onEdit, onDelete, onToggle }) => {
    const typeInfo = MESSAGE_TYPES.find(t => t.id === message.type) || MESSAGE_TYPES[0];
    const Icon = typeInfo.icon;

    return (
        <div className={cn(
            'p-4 rounded-xl border transition-all',
            message.isActive
                ? 'bg-white/5 border-white/20'
                : 'bg-white/2 border-white/10 opacity-60'
        )}>
            <div className="flex items-start gap-4">
                <div className={cn(
                    'p-3 rounded-xl',
                    `bg-${typeInfo.color}-500/20`
                )} style={{ backgroundColor: typeInfo.color === 'emerald' ? 'rgba(16, 185, 129, 0.2)' : typeInfo.color === 'amber' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(139, 92, 246, 0.2)' }}>
                    <Icon className="w-6 h-6" style={{ color: typeInfo.color === 'emerald' ? '#34D399' : typeInfo.color === 'amber' ? '#FBBF24' : '#A78BFA' }} />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-white font-medium">{message.name}</h3>
                        <span className={cn(
                            'text-xs px-2 py-0.5 rounded-full',
                            message.isActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-500/20 text-gray-400'
                        )}>
                            {message.isActive ? 'Ativo' : 'Inativo'}
                        </span>
                    </div>

                    <p className="text-white/50 text-sm mb-2">{typeInfo.description}</p>

                    <div className="p-3 bg-black/20 rounded-lg">
                        <p className="text-white/70 text-sm whitespace-pre-wrap">{message.message}</p>
                    </div>

                    {message.type === 'keyword' && message.triggerKeyword && (
                        <div className="mt-2 flex items-center gap-2">
                            <span className="text-white/40 text-xs">Palavra-chave:</span>
                            <code className="text-emerald-400 text-xs bg-emerald-500/10 px-2 py-0.5 rounded">
                                {message.triggerKeyword}
                            </code>
                        </div>
                    )}

                    {message.type === 'away' && message.scheduleStart && (
                        <div className="mt-2 flex items-center gap-2 text-xs text-white/40">
                            <Clock className="w-3 h-3" />
                            <span>Ativo das {message.scheduleStart} às {message.scheduleEnd || '00:00'}</span>
                        </div>
                    )}
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={() => onToggle(message.id)}
                        className={cn(
                            'p-2 rounded-lg transition-colors',
                            message.isActive
                                ? 'text-emerald-400 hover:bg-emerald-500/20'
                                : 'text-gray-400 hover:bg-gray-500/20'
                        )}
                        title={message.isActive ? 'Desativar' : 'Ativar'}
                    >
                        {message.isActive ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={() => onEdit(message)}
                        className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
                    >
                        <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => onDelete(message.id)}
                        className="p-2 rounded-lg text-white/40 hover:text-red-400 hover:bg-red-500/20 transition-colors"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
};

// Form Modal Component
const AutoMessageForm = ({ isOpen, onClose, onSave, editingMessage }) => {
    const [formData, setFormData] = useState({
        type: 'welcome',
        name: '',
        message: '',
        triggerKeyword: '',
        scheduleStart: '18:00',
        scheduleEnd: '08:00',
        scheduleDays: [0, 6],
        delaySeconds: 0,
        isActive: true
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (editingMessage) {
            setFormData({
                type: editingMessage.type,
                name: editingMessage.name,
                message: editingMessage.message,
                triggerKeyword: editingMessage.triggerKeyword || '',
                scheduleStart: editingMessage.scheduleStart || '18:00',
                scheduleEnd: editingMessage.scheduleEnd || '08:00',
                scheduleDays: editingMessage.scheduleDays || [0, 6],
                delaySeconds: editingMessage.delaySeconds || 0,
                isActive: editingMessage.isActive
            });
        } else {
            setFormData({
                type: 'welcome',
                name: '',
                message: '',
                triggerKeyword: '',
                scheduleStart: '18:00',
                scheduleEnd: '08:00',
                scheduleDays: [0, 6],
                delaySeconds: 0,
                isActive: true
            });
        }
    }, [editingMessage, isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.name.trim() || !formData.message.trim()) {
            toast.error('Preencha todos os campos obrigatórios');
            return;
        }

        if (formData.type === 'keyword' && !formData.triggerKeyword.trim()) {
            toast.error('Informe a palavra-chave');
            return;
        }

        setSaving(true);
        try {
            await onSave(formData, editingMessage?.id);
            onClose();
        } catch (error) {
            toast.error('Erro ao salvar mensagem');
        } finally {
            setSaving(false);
        }
    };

    const toggleDay = (dayId) => {
        const days = formData.scheduleDays || [];
        if (days.includes(dayId)) {
            setFormData({ ...formData, scheduleDays: days.filter(d => d !== dayId) });
        } else {
            setFormData({ ...formData, scheduleDays: [...days, dayId].sort() });
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-lg bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-2">
                        <Bot className="w-5 h-5 text-emerald-400" />
                        <h2 className="text-lg font-semibold text-white">
                            {editingMessage ? 'Editar Mensagem' : 'Nova Mensagem Automática'}
                        </h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4 max-h-[70vh] overflow-y-auto">
                    {/* Type Selection */}
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Tipo de Mensagem</label>
                        <div className="grid grid-cols-3 gap-2">
                            {MESSAGE_TYPES.map(type => (
                                <button
                                    key={type.id}
                                    type="button"
                                    onClick={() => setFormData({ ...formData, type: type.id })}
                                    className={cn(
                                        'p-3 rounded-xl border transition-all text-center',
                                        formData.type === type.id
                                            ? 'border-emerald-500 bg-emerald-500/20'
                                            : 'border-white/10 hover:border-white/30'
                                    )}
                                >
                                    <type.icon className="w-5 h-5 mx-auto mb-1 text-white/70" />
                                    <span className="text-white text-xs">{type.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Name */}
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Nome *</label>
                        <GlassInput
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Ex: Boas-vindas padrão"
                        />
                    </div>

                    {/* Message */}
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Mensagem *</label>
                        <textarea
                            value={formData.message}
                            onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                            placeholder="Digite a mensagem..."
                            rows={4}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                        />
                    </div>

                    {/* Keyword (for keyword type) */}
                    {formData.type === 'keyword' && (
                        <div>
                            <label className="text-white/70 text-sm mb-2 block">Palavra-chave *</label>
                            <GlassInput
                                type="text"
                                value={formData.triggerKeyword}
                                onChange={(e) => setFormData({ ...formData, triggerKeyword: e.target.value })}
                                placeholder="Ex: preço, orçamento, horário"
                            />
                        </div>
                    )}

                    {/* Schedule (for away type) */}
                    {formData.type === 'away' && (
                        <>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="text-white/70 text-sm mb-2 block">Início</label>
                                    <GlassInput
                                        type="time"
                                        value={formData.scheduleStart}
                                        onChange={(e) => setFormData({ ...formData, scheduleStart: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="text-white/70 text-sm mb-2 block">Fim</label>
                                    <GlassInput
                                        type="time"
                                        value={formData.scheduleEnd}
                                        onChange={(e) => setFormData({ ...formData, scheduleEnd: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="text-white/70 text-sm mb-2 block">Dias ativos</label>
                                <div className="flex gap-2">
                                    {DAYS_OF_WEEK.map(day => (
                                        <button
                                            key={day.id}
                                            type="button"
                                            onClick={() => toggleDay(day.id)}
                                            className={cn(
                                                'w-10 h-10 rounded-lg text-sm font-medium transition-colors',
                                                (formData.scheduleDays || []).includes(day.id)
                                                    ? 'bg-emerald-500 text-white'
                                                    : 'bg-white/10 text-white/50 hover:text-white'
                                            )}
                                        >
                                            {day.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    {/* Delay */}
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">
                            Delay antes de enviar (segundos)
                        </label>
                        <GlassInput
                            type="number"
                            min="0"
                            max="60"
                            value={formData.delaySeconds}
                            onChange={(e) => setFormData({ ...formData, delaySeconds: parseInt(e.target.value) || 0 })}
                        />
                    </div>

                    {/* Submit */}
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
                            {saving ? 'Salvando...' : editingMessage ? 'Atualizar' : 'Criar'}
                        </GlassButton>
                    </div>
                </form>
            </div>
        </div>
    );
};

const Automations = () => {
    const { user } = useAuthStore();
    const [loading, setLoading] = useState(true);
    const [messages, setMessages] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [editingMessage, setEditingMessage] = useState(null);

    const tenantId = user?.tenantId || 'tenant-1';

    const loadMessages = useCallback(async () => {
        try {
            setLoading(true);
            const data = await AutoMessagesAPI.list(tenantId);
            setMessages(data);
        } catch (error) {
            console.error('Error loading auto messages:', error);
            toast.error('Erro ao carregar mensagens');
        } finally {
            setLoading(false);
        }
    }, [tenantId]);

    useEffect(() => {
        loadMessages();
    }, [loadMessages]);

    const handleSave = async (formData, editId) => {
        if (editId) {
            await AutoMessagesAPI.update(editId, formData);
            toast.success('Mensagem atualizada');
        } else {
            await AutoMessagesAPI.create(tenantId, formData);
            toast.success('Mensagem criada');
        }
        loadMessages();
    };

    const handleEdit = (message) => {
        setEditingMessage(message);
        setShowForm(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Deseja realmente excluir esta mensagem automática?')) return;

        try {
            await AutoMessagesAPI.delete(id);
            toast.success('Mensagem excluída');
            loadMessages();
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    const handleToggle = async (id) => {
        try {
            const result = await AutoMessagesAPI.toggle(id);
            toast.success(result.isActive ? 'Mensagem ativada' : 'Mensagem desativada');
            loadMessages();
        } catch (error) {
            toast.error('Erro ao alterar status');
        }
    };

    const closeForm = () => {
        setShowForm(false);
        setEditingMessage(null);
    };

    return (
        <div className="p-6 overflow-y-auto h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Bot className="w-8 h-8 text-emerald-400" />
                        Automações
                    </h1>
                    <p className="text-white/50 mt-1">Configure mensagens automáticas para seu atendimento</p>
                </div>
                <GlassButton onClick={() => setShowForm(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Nova Mensagem
                </GlassButton>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : messages.length === 0 ? (
                <GlassCard className="p-12 text-center">
                    <Bot className="w-16 h-16 text-white/20 mx-auto mb-4" />
                    <h3 className="text-xl font-medium text-white mb-2">Nenhuma mensagem automática</h3>
                    <p className="text-white/50 mb-6">
                        Configure mensagens de boas-vindas, fora do horário e respostas por palavra-chave.
                    </p>
                    <GlassButton onClick={() => setShowForm(true)}>
                        <Plus className="w-4 h-4 mr-2" />
                        Criar primeira mensagem
                    </GlassButton>
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {messages.map(message => (
                        <AutoMessageCard
                            key={message.id}
                            message={message}
                            onEdit={handleEdit}
                            onDelete={handleDelete}
                            onToggle={handleToggle}
                        />
                    ))}
                </div>
            )}

            {/* Form Modal */}
            <AutoMessageForm
                isOpen={showForm}
                onClose={closeForm}
                onSave={handleSave}
                editingMessage={editingMessage}
            />
        </div>
    );
};

export default Automations;
