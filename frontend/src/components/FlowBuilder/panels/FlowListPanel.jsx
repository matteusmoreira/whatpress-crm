import React, { useState } from 'react';
import useFlowStore from '../../../store/flowStore';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Trash2, Copy, Play, Pause, Plus } from 'lucide-react';
import { toast } from 'sonner';

const FlowListPanel = () => {
    const {
        flows,
        currentFlow,
        setCurrentFlow,
        fetchFlow,
        deleteFlow,
        duplicateFlow,
        toggleFlow,
        clearCanvas
    } = useFlowStore();

    const [duplicateName, setDuplicateName] = useState('');
    const [duplicatingId, setDuplicatingId] = useState(null);

    const handleLoadFlow = async (flowId) => {
        await fetchFlow(flowId);
        toast.success('Fluxo carregado');
    };

    const handleNewFlow = () => {
        clearCanvas();
        toast.info('Novo fluxo criado. Configure e salve.');
    };

    const handleDeleteFlow = async (flowId, flowName) => {
        if (window.confirm(`Tem certeza que deseja deletar o fluxo "${flowName}"?`)) {
            const success = await deleteFlow(flowId);
            if (success) {
                toast.success('Fluxo deletado');
            } else {
                toast.error('Erro ao deletar fluxo');
            }
        }
    };

    const handleDuplicateFlow = async (flowId) => {
        if (!duplicateName.trim()) {
            toast.error('Digite um nome para a cópia');
            return;
        }

        const result = await duplicateFlow(flowId, duplicateName);
        if (result) {
            toast.success('Fluxo duplicado');
            setDuplicatingId(null);
            setDuplicateName('');
        } else {
            toast.error('Erro ao duplicar fluxo');
        }
    };

    const handleToggleFlow = async (flowId, flowName) => {
        const result = await toggleFlow(flowId);
        if (result) {
            toast.success(result.message);
        } else {
            toast.error('Erro ao alterar status do fluxo');
        }
    };

    return (
        <div className="flow-list-panel">
            <div className="panel-header">
                <h3>Fluxos</h3>
                <Button
                    size="sm"
                    onClick={handleNewFlow}
                    className="new-flow-btn"
                >
                    <Plus size={16} />
                    Novo
                </Button>
            </div>

            <div className="flow-list">
                {flows.length === 0 ? (
                    <div className="empty-state">
                        <p>Nenhum fluxo encontrado</p>
                        <p className="text-xs text-muted-foreground mt-2">
                            Crie seu primeiro fluxo clicando em "Novo"
                        </p>
                    </div>
                ) : (
                    flows.map((flow) => (
                        <div
                            key={flow.id}
                            className={`flow-item ${currentFlow?.id === flow.id ? 'active' : ''}`}
                        >
                            <div
                                className="flow-item-main"
                                onClick={() => handleLoadFlow(flow.id)}
                            >
                                <div className="flow-item-header">
                                    <span className="flow-name">{flow.name}</span>
                                    {flow.isActive && (
                                        <span className="flow-badge active">Ativo</span>
                                    )}
                                </div>
                                {flow.description && (
                                    <p className="flow-description">{flow.description}</p>
                                )}
                                <div className="flow-meta">
                                    <span className="flow-status">{flow.status}</span>
                                    <span className="flow-date">
                                        {new Date(flow.updatedAt).toLocaleDateString()}
                                    </span>
                                </div>
                            </div>

                            <div className="flow-item-actions">
                                <button
                                    onClick={() => handleToggleFlow(flow.id, flow.name)}
                                    className="flow-action-btn"
                                    title={flow.isActive ? 'Desativar' : 'Ativar'}
                                >
                                    {flow.isActive ? <Pause size={14} /> : <Play size={14} />}
                                </button>

                                <button
                                    onClick={() => {
                                        setDuplicatingId(flow.id);
                                        setDuplicateName(`${flow.name} (Cópia)`);
                                    }}
                                    className="flow-action-btn"
                                    title="Duplicar"
                                >
                                    <Copy size={14} />
                                </button>

                                <button
                                    onClick={() => handleDeleteFlow(flow.id, flow.name)}
                                    className="flow-action-btn delete"
                                    title="Deletar"
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>

                            {duplicatingId === flow.id && (
                                <div className="duplicate-form">
                                    <Input
                                        value={duplicateName}
                                        onChange={(e) => setDuplicateName(e.target.value)}
                                        placeholder="Nome da cópia"
                                        className="duplicate-input"
                                    />
                                    <div className="duplicate-actions">
                                        <Button
                                            size="sm"
                                            onClick={() => handleDuplicateFlow(flow.id)}
                                        >
                                            Duplicar
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => {
                                                setDuplicatingId(null);
                                                setDuplicateName('');
                                            }}
                                        >
                                            Cancelar
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default FlowListPanel;
