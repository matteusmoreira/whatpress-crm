import React, { useState, useEffect, useCallback } from 'react';
import {
    Bot,
    Plus,
    Edit2,
    Trash2,
    Power,
    PowerOff,
    MessageSquare,
    ListOrdered,
    ArrowRight,
    Users,
    Clock,
    X,
    Check,
    ChevronDown,
    ChevronRight,
    Zap
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton } from '../components/GlassCard';
import { useAuthStore } from '../store/authStore';
import { ChatbotAPI, AgentsAPI } from '../lib/api';
import { toast } from '../components/ui/glass-toaster';
import { cn } from '../lib/utils';

const TRIGGER_TYPES = [
    { id: 'new_conversation', label: 'Nova Conversa', icon: MessageSquare, description: 'Ativa quando uma nova conversa começa' },
    { id: 'keyword', label: 'Palavra-chave', icon: Zap, description: 'Ativa quando detectar palavras específicas' },
    { id: 'menu_option', label: 'Opção de Menu', icon: ListOrdered, description: 'Ativa quando o usuário escolher uma opção' }
];

const STEP_TYPES = [
    { id: 'message', label: 'Mensagem', icon: MessageSquare, description: 'Enviar uma mensagem' },
    { id: 'menu', label: 'Menu', icon: ListOrdered, description: 'Mostrar opções para o usuário' },
    { id: 'wait_input', label: 'Aguardar Resposta', icon: Clock, description: 'Aguardar entrada do usuário' },
    { id: 'transfer', label: 'Transferir', icon: Users, description: 'Transferir para um agente' }
];

// Flow Card Component
const FlowCard = ({ flow, onEdit, onDelete, onToggle, onViewSteps }) => {
    const trigger = TRIGGER_TYPES.find(t => t.id === flow.triggerType) || TRIGGER_TYPES[0];
    const TriggerIcon = trigger.icon;

    return (
        <div className={cn(
            'p-4 rounded-xl border transition-all',
            flow.isActive
                ? 'bg-white/5 border-white/20 hover:border-emerald-500/50'
                : 'bg-white/2 border-white/10 opacity-60'
        )}>
            <div className="flex items-start gap-4">
                <div className="p-3 rounded-xl bg-purple-500/20">
                    <Bot className="w-6 h-6 text-purple-400" />
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-white font-medium">{flow.name}</h3>
                        <span className={cn(
                            'text-xs px-2 py-0.5 rounded-full',
                            flow.isActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-gray-500/20 text-gray-400'
                        )}>
                            {flow.isActive ? 'Ativo' : 'Inativo'}
                        </span>
                    </div>

                    {flow.description && (
                        <p className="text-white/50 text-sm mb-2">{flow.description}</p>
                    )}

                    <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1 text-white/40">
                            <TriggerIcon className="w-3 h-3" />
                            <span>{trigger.label}</span>
                            {flow.triggerValue && (
                                <code className="ml-1 px-1 py-0.5 rounded bg-white/10 text-emerald-400 text-xs">
                                    {flow.triggerValue}
                                </code>
                            )}
                        </div>
                        <div className="flex items-center gap-1 text-white/40">
                            <ListOrdered className="w-3 h-3" />
                            <span>{flow.stepsCount || 0} passos</span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        onClick={() => onViewSteps(flow)}
                        className="p-2 rounded-lg text-white/40 hover:text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                        title="Ver passos"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => onToggle(flow.id)}
                        className={cn(
                            'p-2 rounded-lg transition-colors',
                            flow.isActive
                                ? 'text-emerald-400 hover:bg-emerald-500/20'
                                : 'text-gray-400 hover:bg-gray-500/20'
                        )}
                        title={flow.isActive ? 'Desativar' : 'Ativar'}
                    >
                        {flow.isActive ? <Power className="w-4 h-4" /> : <PowerOff className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={() => onEdit(flow)}
                        className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
                    >
                        <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                        onClick={() => onDelete(flow.id)}
                        className="p-2 rounded-lg text-white/40 hover:text-red-400 hover:bg-red-500/20 transition-colors"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </div>
    );
};

// Flow Form Modal
const FlowFormModal = ({ isOpen, onClose, onSave, editingFlow }) => {
    const [formData, setFormData] = useState({
        name: '',
        description: '',
        triggerType: 'new_conversation',
        triggerValue: '',
        isActive: true,
        priority: 0
    });
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (editingFlow) {
            setFormData({
                name: editingFlow.name,
                description: editingFlow.description || '',
                triggerType: editingFlow.triggerType,
                triggerValue: editingFlow.triggerValue || '',
                isActive: editingFlow.isActive,
                priority: editingFlow.priority || 0
            });
        } else {
            setFormData({
                name: '',
                description: '',
                triggerType: 'new_conversation',
                triggerValue: '',
                isActive: true,
                priority: 0
            });
        }
    }, [editingFlow, isOpen]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.name.trim()) {
            toast.error('Informe o nome do fluxo');
            return;
        }

        setSaving(true);
        try {
            await onSave(formData, editingFlow?.id);
            onClose();
        } catch (error) {
            toast.error('Erro ao salvar fluxo');
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-lg bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div className="flex items-center gap-2">
                        <Bot className="w-5 h-5 text-purple-400" />
                        <h2 className="text-lg font-semibold text-white">
                            {editingFlow ? 'Editar Fluxo' : 'Novo Fluxo de Chatbot'}
                        </h2>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-4 space-y-4">
                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Nome do Fluxo *</label>
                        <GlassInput
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="Ex: Atendimento Inicial"
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Descrição</label>
                        <textarea
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                            placeholder="Descrição do fluxo..."
                            rows={2}
                            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 resize-none"
                        />
                    </div>

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Gatilho</label>
                        <div className="grid grid-cols-3 gap-2">
                            {TRIGGER_TYPES.map(type => (
                                <button
                                    key={type.id}
                                    type="button"
                                    onClick={() => setFormData({ ...formData, triggerType: type.id })}
                                    className={cn(
                                        'p-3 rounded-xl border transition-all text-center',
                                        formData.triggerType === type.id
                                            ? 'border-purple-500 bg-purple-500/20'
                                            : 'border-white/10 hover:border-white/30'
                                    )}
                                >
                                    <type.icon className="w-5 h-5 mx-auto mb-1 text-white/70" />
                                    <span className="text-white text-xs">{type.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {formData.triggerType === 'keyword' && (
                        <div>
                            <label className="text-white/70 text-sm mb-2 block">Palavra-chave</label>
                            <GlassInput
                                type="text"
                                value={formData.triggerValue}
                                onChange={(e) => setFormData({ ...formData, triggerValue: e.target.value })}
                                placeholder="Ex: menu, ajuda, suporte"
                            />
                        </div>
                    )}

                    <div>
                        <label className="text-white/70 text-sm mb-2 block">Prioridade</label>
                        <GlassInput
                            type="number"
                            min="0"
                            max="100"
                            value={formData.priority}
                            onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 0 })}
                        />
                        <p className="text-white/30 text-xs mt-1">Maior prioridade = executado primeiro</p>
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
                            {saving ? 'Salvando...' : editingFlow ? 'Atualizar' : 'Criar Fluxo'}
                        </GlassButton>
                    </div>
                </form>
            </div>
        </div>
    );
};

// Steps Editor Panel
const StepsEditorPanel = ({ flow, onClose, onUpdate }) => {
    const [steps, setSteps] = useState([]);
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingStep, setEditingStep] = useState(null);
    const { user } = useAuthStore();

    useEffect(() => {
        const loadData = async () => {
            try {
                const [flowData, agentsData] = await Promise.all([
                    ChatbotAPI.getFlow(flow.id),
                    AgentsAPI.list(user?.tenantId)
                ]);
                setSteps(flowData.steps || []);
                setAgents(agentsData || []);
            } catch (error) {
                console.error('Error loading flow data:', error);
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [flow.id, user?.tenantId]);

    const addStep = async (stepType) => {
        try {
            const newStep = await ChatbotAPI.addStep(flow.id, {
                step_order: steps.length + 1,
                step_type: stepType,
                message: stepType === 'message' ? 'Nova mensagem' : null,
                menu_options: stepType === 'menu' ? [{ key: '1', label: 'Opção 1' }] : null
            });
            setSteps([...steps, { ...newStep, stepType, message: 'Nova mensagem' }]);
            toast.success('Passo adicionado');
        } catch (error) {
            toast.error('Erro ao adicionar passo');
        }
    };

    const deleteStep = async (stepId) => {
        if (!window.confirm('Excluir este passo?')) return;
        try {
            await ChatbotAPI.deleteStep(stepId);
            setSteps(steps.filter(s => s.id !== stepId));
            toast.success('Passo excluído');
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-end lg:items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-2xl max-h-[90vh] bg-emerald-950/95 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl overflow-hidden">
                <div className="flex items-center justify-between p-4 border-b border-white/10">
                    <div>
                        <h2 className="text-lg font-semibold text-white">Passos do Fluxo</h2>
                        <p className="text-white/50 text-sm">{flow.name}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-white/10 rounded-lg text-white/60">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-4 overflow-y-auto max-h-[60vh]">
                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                        </div>
                    ) : steps.length === 0 ? (
                        <div className="text-center py-8 text-white/40">
                            <ListOrdered className="w-12 h-12 mx-auto mb-2 opacity-50" />
                            <p>Nenhum passo configurado</p>
                            <p className="text-sm">Adicione passos abaixo para criar o fluxo</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {steps.map((step, index) => {
                                const stepType = STEP_TYPES.find(t => t.id === step.stepType) || STEP_TYPES[0];
                                const StepIcon = stepType.icon;

                                return (
                                    <div key={step.id} className="relative">
                                        {index > 0 && (
                                            <div className="absolute left-6 -top-3 w-0.5 h-3 bg-white/20" />
                                        )}
                                        <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg border border-white/10">
                                            <div className="p-2 rounded-lg bg-purple-500/20">
                                                <StepIcon className="w-4 h-4 text-purple-400" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-white/40 text-xs">Passo {index + 1}</span>
                                                    <span className="text-white text-sm font-medium">{stepType.label}</span>
                                                </div>
                                                {step.message && (
                                                    <p className="text-white/60 text-sm truncate">{step.message}</p>
                                                )}
                                                {step.stepType === 'menu' && step.menuOptions && (
                                                    <div className="flex gap-1 mt-1">
                                                        {step.menuOptions.map((opt, i) => (
                                                            <span key={i} className="text-xs px-1.5 py-0.5 bg-white/10 rounded">
                                                                {opt.key}: {opt.label}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            <button
                                                onClick={() => deleteStep(step.id)}
                                                className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/20 rounded"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                        {index < steps.length - 1 && (
                                            <div className="flex justify-center my-1">
                                                <ArrowRight className="w-4 h-4 text-white/20 rotate-90" />
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Add Step Buttons */}
                <div className="p-4 border-t border-white/10">
                    <p className="text-white/50 text-sm mb-2">Adicionar passo:</p>
                    <div className="flex flex-wrap gap-2">
                        {STEP_TYPES.map(type => (
                            <button
                                key={type.id}
                                onClick={() => addStep(type.id)}
                                className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-white/70 hover:text-white text-sm transition-colors"
                            >
                                <type.icon className="w-4 h-4" />
                                {type.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

const Chatbot = () => {
    const { user } = useAuthStore();
    const [loading, setLoading] = useState(true);
    const [flows, setFlows] = useState([]);
    const [showFlowForm, setShowFlowForm] = useState(false);
    const [editingFlow, setEditingFlow] = useState(null);
    const [selectedFlow, setSelectedFlow] = useState(null);

    const tenantId = user?.tenantId || 'tenant-1';

    const loadFlows = useCallback(async () => {
        try {
            setLoading(true);
            const data = await ChatbotAPI.listFlows(tenantId);
            setFlows(data);
        } catch (error) {
            console.error('Error loading chatbot flows:', error);
            toast.error('Erro ao carregar fluxos');
        } finally {
            setLoading(false);
        }
    }, [tenantId]);

    useEffect(() => {
        loadFlows();
    }, [loadFlows]);

    const handleSaveFlow = async (formData, editId) => {
        if (editId) {
            await ChatbotAPI.updateFlow(editId, formData);
            toast.success('Fluxo atualizado');
        } else {
            await ChatbotAPI.createFlow(tenantId, formData);
            toast.success('Fluxo criado');
        }
        loadFlows();
    };

    const handleEditFlow = (flow) => {
        setEditingFlow(flow);
        setShowFlowForm(true);
    };

    const handleDeleteFlow = async (id) => {
        if (!window.confirm('Deseja excluir este fluxo e todos os seus passos?')) return;

        try {
            await ChatbotAPI.deleteFlow(id);
            toast.success('Fluxo excluído');
            loadFlows();
        } catch (error) {
            toast.error('Erro ao excluir');
        }
    };

    const handleToggleFlow = async (id) => {
        try {
            const result = await ChatbotAPI.toggleFlow(id);
            toast.success(result.isActive ? 'Fluxo ativado' : 'Fluxo desativado');
            loadFlows();
        } catch (error) {
            toast.error('Erro ao alterar status');
        }
    };

    const closeFlowForm = () => {
        setShowFlowForm(false);
        setEditingFlow(null);
    };

    return (
        <div className="p-6 overflow-y-auto h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Bot className="w-8 h-8 text-purple-400" />
                        Chatbot
                    </h1>
                    <p className="text-white/50 mt-1">Configure fluxos de atendimento automatizado</p>
                </div>
                <GlassButton onClick={() => setShowFlowForm(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Novo Fluxo
                </GlassButton>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-12">
                    <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                </div>
            ) : flows.length === 0 ? (
                <GlassCard className="p-12 text-center">
                    <Bot className="w-16 h-16 text-white/20 mx-auto mb-4" />
                    <h3 className="text-xl font-medium text-white mb-2">Nenhum fluxo de chatbot</h3>
                    <p className="text-white/50 mb-6">
                        Crie fluxos para automatizar o atendimento inicial, menus e transferências.
                    </p>
                    <GlassButton onClick={() => setShowFlowForm(true)}>
                        <Plus className="w-4 h-4 mr-2" />
                        Criar primeiro fluxo
                    </GlassButton>
                </GlassCard>
            ) : (
                <div className="space-y-4">
                    {flows.map(flow => (
                        <FlowCard
                            key={flow.id}
                            flow={flow}
                            onEdit={handleEditFlow}
                            onDelete={handleDeleteFlow}
                            onToggle={handleToggleFlow}
                            onViewSteps={setSelectedFlow}
                        />
                    ))}
                </div>
            )}

            {/* Modals */}
            <FlowFormModal
                isOpen={showFlowForm}
                onClose={closeFlowForm}
                onSave={handleSaveFlow}
                editingFlow={editingFlow}
            />

            {selectedFlow && (
                <StepsEditorPanel
                    flow={selectedFlow}
                    onClose={() => setSelectedFlow(null)}
                    onUpdate={loadFlows}
                />
            )}
        </div>
    );
};

export default Chatbot;
