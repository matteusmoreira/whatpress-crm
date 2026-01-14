import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Edit2, Trash2, Check, Tag } from 'lucide-react';
import { GlassInput, GlassButton } from './GlassCard';
import { LabelsAPI } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { toast } from './ui/glass-toaster';
import { cn } from '../lib/utils';

// Predefined colors for quick selection
const PRESET_COLORS = [
    '#EF4444', '#F59E0B', '#10B981', '#3B82F6',
    '#8B5CF6', '#EC4899', '#06B6D4', '#6366F1',
    '#14B8A6', '#F97316', '#84CC16', '#A855F7'
];

const LabelsManager = ({ isOpen, onClose, onLabelsChange }) => {
    const { user } = useAuthStore();
    const [labels, setLabels] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);
    const [showNewForm, setShowNewForm] = useState(false);
    const [formData, setFormData] = useState({ name: '', color: '#3B82F6' });
    const [saving, setSaving] = useState(false);

    const tenantId = user?.tenantId;

    const loadLabels = useCallback(async () => {
        try {
            if (!tenantId) return;
            setLoading(true);
            const data = await LabelsAPI.list(tenantId);
            setLabels(data);
        } catch (error) {
            console.error('Error loading labels:', error);
            toast.error('Erro ao carregar labels');
        } finally {
            setLoading(false);
        }
    }, [tenantId]);

    useEffect(() => {
        if (isOpen) {
            loadLabels();
        }
    }, [isOpen, loadLabels]);

    const handleCreate = async () => {
        if (!formData.name.trim()) {
            toast.error('Digite um nome para a label');
            return;
        }

        try {
            setSaving(true);
            const newLabel = await LabelsAPI.create(tenantId, formData);
            setLabels([...labels, newLabel]);
            setFormData({ name: '', color: '#3B82F6' });
            setShowNewForm(false);
            toast.success('Label criada com sucesso');
            onLabelsChange?.();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao criar label');
        } finally {
            setSaving(false);
        }
    };

    const handleUpdate = async (labelId) => {
        if (!formData.name.trim()) {
            toast.error('Digite um nome para a label');
            return;
        }

        try {
            setSaving(true);
            const updated = await LabelsAPI.update(labelId, formData);
            setLabels(labels.map(l => l.id === labelId ? { ...l, ...updated } : l));
            setEditingId(null);
            setFormData({ name: '', color: '#3B82F6' });
            toast.success('Label atualizada');
            onLabelsChange?.();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao atualizar label');
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (labelId) => {
        const label = labels.find(l => l.id === labelId);
        if (label?.usageCount > 0) {
            const confirm = window.confirm(
                `Esta label está sendo usada em ${label.usageCount} conversa(s). Deseja remover mesmo assim?`
            );
            if (!confirm) return;
        }

        try {
            await LabelsAPI.delete(labelId);
            setLabels(labels.filter(l => l.id !== labelId));
            toast.success('Label removida');
            onLabelsChange?.();
        } catch (error) {
            toast.error('Erro ao remover label');
        }
    };

    const startEdit = (label) => {
        setEditingId(label.id);
        setFormData({ name: label.name, color: label.color });
        setShowNewForm(false);
    };

    const cancelEdit = () => {
        setEditingId(null);
        setFormData({ name: '', color: '#3B82F6' });
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-md bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-2">
                        <Tag className="w-5 h-5 text-emerald-400" />
                        <h2 className="text-lg font-semibold text-white">Gerenciar Labels</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-white/10 rounded-lg text-white/60 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-4 max-h-96 overflow-y-auto">
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {labels.map((label) => (
                                <div key={label.id}>
                                    {editingId === label.id ? (
                                        /* Edit Form */
                                        <div className="p-3 bg-white/5 rounded-xl space-y-3">
                                            <GlassInput
                                                type="text"
                                                value={formData.name}
                                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                                placeholder="Nome da label"
                                                className="text-sm"
                                            />
                                            <div className="flex flex-wrap gap-2">
                                                {PRESET_COLORS.map((color) => (
                                                    <button
                                                        key={color}
                                                        onClick={() => setFormData({ ...formData, color })}
                                                        className={cn(
                                                            'w-6 h-6 rounded-full transition-transform',
                                                            formData.color === color && 'ring-2 ring-white scale-110'
                                                        )}
                                                        style={{ backgroundColor: color }}
                                                    />
                                                ))}
                                            </div>
                                            <div className="flex gap-2">
                                                <GlassButton
                                                    onClick={() => handleUpdate(label.id)}
                                                    disabled={saving}
                                                    className="flex-1 text-sm py-2"
                                                >
                                                    <Check className="w-4 h-4 mr-1" />
                                                    Salvar
                                                </GlassButton>
                                                <button
                                                    onClick={cancelEdit}
                                                    className="px-4 py-2 text-sm text-white/60 hover:text-white transition-colors"
                                                >
                                                    Cancelar
                                                </button>
                                            </div>
                                        </div>
                                    ) : (
                                        /* Label Item */
                                        <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors">
                                            <div className="flex items-center gap-3">
                                                <span
                                                    className="w-4 h-4 rounded-full"
                                                    style={{ backgroundColor: label.color }}
                                                />
                                                <span className="text-white font-medium">{label.name}</span>
                                                {label.usageCount > 0 && (
                                                    <span className="text-xs text-white/40 bg-white/10 px-2 py-0.5 rounded-full">
                                                        {label.usageCount}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <button
                                                    onClick={() => startEdit(label)}
                                                    className="p-2 hover:bg-white/10 rounded-lg text-white/40 hover:text-white transition-colors"
                                                >
                                                    <Edit2 className="w-4 h-4" />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(label.id)}
                                                    className="p-2 hover:bg-red-500/20 rounded-lg text-white/40 hover:text-red-400 transition-colors"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}

                            {/* New Label Form */}
                            {showNewForm ? (
                                <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl space-y-3">
                                    <GlassInput
                                        type="text"
                                        value={formData.name}
                                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                        placeholder="Nome da nova label"
                                        className="text-sm"
                                        autoFocus
                                    />
                                    <div className="flex flex-wrap gap-2">
                                        {PRESET_COLORS.map((color) => (
                                            <button
                                                key={color}
                                                onClick={() => setFormData({ ...formData, color })}
                                                className={cn(
                                                    'w-6 h-6 rounded-full transition-transform',
                                                    formData.color === color && 'ring-2 ring-white scale-110'
                                                )}
                                                style={{ backgroundColor: color }}
                                            />
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <GlassButton
                                            onClick={handleCreate}
                                            disabled={saving}
                                            className="flex-1 text-sm py-2"
                                        >
                                            <Plus className="w-4 h-4 mr-1" />
                                            Criar Label
                                        </GlassButton>
                                        <button
                                            onClick={() => {
                                                setShowNewForm(false);
                                                setFormData({ name: '', color: '#3B82F6' });
                                            }}
                                            className="px-4 py-2 text-sm text-white/60 hover:text-white transition-colors"
                                        >
                                            Cancelar
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                <button
                                    onClick={() => setShowNewForm(true)}
                                    className="w-full p-3 border-2 border-dashed border-white/20 rounded-xl text-white/50 hover:text-white hover:border-emerald-500/50 transition-all flex items-center justify-center gap-2"
                                >
                                    <Plus className="w-4 h-4" />
                                    Nova Label
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-white/10">
                    <p className="text-xs text-white/40 text-center">
                        Labels são usadas para organizar suas conversas
                    </p>
                </div>
            </div>
        </div>
    );
};

export default LabelsManager;
