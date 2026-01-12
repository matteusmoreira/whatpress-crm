import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import './FlowBuilder.css';
import { Plus, Save, Play, Trash2, Settings, X, MessageSquare, Image, Clock, GitBranch, Variable, Webhook, ChevronRight } from 'lucide-react';
import useFlowStore from '../store/flowStore';
import { GlassCard } from '../components/GlassCard';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';

// Import custom nodes
import StartNode from '../components/FlowBuilder/nodes/StartNode';
import TextMessageNode from '../components/FlowBuilder/nodes/TextMessageNode';
import MediaMessageNode from '../components/FlowBuilder/nodes/MediaMessageNode';
import WaitNode from '../components/FlowBuilder/nodes/WaitNode';
import ConditionalNode from '../components/FlowBuilder/nodes/ConditionalNode';
import VariableNode from '../components/FlowBuilder/nodes/VariableNode';
import WebhookNode from '../components/FlowBuilder/nodes/WebhookNode';

const nodeTypes = {
    start: StartNode,
    textMessage: TextMessageNode,
    mediaMessage: MediaMessageNode,
    wait: WaitNode,
    conditional: ConditionalNode,
    variable: VariableNode,
    webhook: WebhookNode,
};

// Node categories for the toolbar
const nodeCategories = [
    {
        title: 'GATILHOS',
        items: [
            { type: 'start', icon: Play, label: 'Início', description: 'Ponto de partida do fluxo', color: 'emerald' }
        ]
    },
    {
        title: 'AÇÕES',
        items: [
            { type: 'textMessage', icon: MessageSquare, label: 'Enviar Texto', description: 'Envia uma mensagem de texto', color: 'blue' },
            { type: 'mediaMessage', icon: Image, label: 'Enviar Mídia', description: 'Envia imagem, vídeo ou documento', color: 'purple' },
        ]
    },
    {
        title: 'CONTROLE',
        items: [
            { type: 'wait', icon: Clock, label: 'Esperar', description: 'Aguarda um tempo antes de continuar', color: 'amber' },
            { type: 'conditional', icon: GitBranch, label: 'Condicional', description: 'Ramifica o fluxo baseado em condição', color: 'pink' },
        ]
    },
    {
        title: 'DADOS',
        items: [
            { type: 'variable', icon: Variable, label: 'Variável', description: 'Define ou modifica variáveis', color: 'cyan' },
            { type: 'webhook', icon: Webhook, label: 'Webhook', description: 'Envia dados para uma URL externa', color: 'indigo' },
        ]
    }
];

const FlowBuilder = () => {
    const { theme } = useTheme();
    const isDark = theme !== 'light';
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNodeState] = useState(null);

    const {
        nodes: storeNodes,
        edges: storeEdges,
        setNodes: setStoreNodes,
        setEdges: setStoreEdges,
        setSelectedNode,
        fetchFlows,
        flows,
        currentFlow,
        setCurrentFlow,
        createFlow,
        saveFlow,
        deleteFlow,
        error: storeError
    } = useFlowStore();

    // Sincronizar nodes e edges do React Flow com o store
    useEffect(() => {
        setNodes(storeNodes);
    }, [storeNodes, setNodes]);

    useEffect(() => {
        setEdges(storeEdges);
    }, [storeEdges, setEdges]);

    useEffect(() => {
        fetchFlows();
    }, [fetchFlows]);

    const handleNodesChange = useCallback(
        (changes) => {
            onNodesChange(changes);
            const updatedNodes = nodes.map(node => {
                const change = changes.find(c => c.id === node.id);
                if (change) {
                    if (change.type === 'position' && change.position) {
                        return { ...node, position: change.position };
                    } else if (change.type === 'select') {
                        if (change.selected) {
                            setSelectedNode(node);
                            setSelectedNodeState(node);
                        }
                    } else if (change.type === 'remove') {
                        return null;
                    }
                }
                return node;
            }).filter(Boolean);
            setStoreNodes(updatedNodes);
        },
        [nodes, onNodesChange, setStoreNodes, setSelectedNode]
    );

    const handleEdgesChange = useCallback(
        (changes) => {
            onEdgesChange(changes);
            const updatedEdges = edges.map(edge => {
                const change = changes.find(c => c.id === edge.id);
                if (change && change.type === 'remove') {
                    return null;
                }
                return edge;
            }).filter(Boolean);
            setStoreEdges(updatedEdges);
        },
        [edges, onEdgesChange, setStoreEdges]
    );

    const onConnect = useCallback(
        (params) => {
            const newEdge = {
                ...params,
                id: `edge_${params.source}_${params.target}_${Date.now()}`,
                type: 'smoothstep',
                animated: true
            };
            setEdges((eds) => addEdge(newEdge, eds));
            setStoreEdges([...edges, newEdge]);
        },
        [setEdges, edges, setStoreEdges]
    );

    const onNodeClick = useCallback((event, node) => {
        setSelectedNode(node);
        setSelectedNodeState(node);
    }, [setSelectedNode]);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
        setSelectedNodeState(null);
    }, [setSelectedNode]);

    const handleCreateFlow = async () => {
        const name = `Novo Fluxo ${(flows?.length || 0) + 1}`;
        const result = await createFlow({ name, description: '' });
        if (result) {
            toast.success('Fluxo criado!');
        } else {
            const errorState = useFlowStore.getState().error;
            toast.error(errorState || 'Erro ao criar fluxo. Verifique o console.');
        }
    };

    const handleSaveFlow = async () => {
        if (!currentFlow) {
            toast.error('Selecione um fluxo primeiro');
            return;
        }
        await saveFlow();
        toast.success('Fluxo salvo!');
    };

    const handleDeleteFlow = async (flowId) => {
        await deleteFlow(flowId);
        toast.success('Fluxo excluído!');
    };

    const handleAddNode = (type) => {
        if (!currentFlow) {
            toast.error('Selecione ou crie um fluxo primeiro');
            return;
        }
        const newNode = {
            id: `${type}_${Date.now()}`,
            type,
            position: { x: 250, y: 100 + (nodes.length * 80) },
            data: { label: type }
        };
        setStoreNodes([...nodes, newNode]);
    };

    return (
        <div className="flex h-full overflow-hidden">
            {/* Left Panel - Flow List */}
            <div className={cn(
                "w-64 flex-shrink-0 border-r flex flex-col",
                isDark ? "bg-slate-900/50 border-white/10" : "bg-white border-slate-200"
            )}>
                {/* Header */}
                <div className={cn(
                    "p-4 border-b flex items-center justify-between",
                    isDark ? "border-white/10" : "border-slate-200"
                )}>
                    <h2 className={cn(
                        "font-semibold",
                        isDark ? "text-white" : "text-slate-800"
                    )}>Fluxos</h2>
                    <button
                        onClick={handleCreateFlow}
                        className={cn(
                            "flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            "bg-emerald-500 hover:bg-emerald-600 text-white"
                        )}
                    >
                        <Plus className="w-4 h-4" />
                        Novo
                    </button>
                </div>

                {/* Flow List */}
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {(!flows || flows.length === 0) ? (
                        <div className={cn(
                            "text-center py-8 px-4",
                            isDark ? "text-white/50" : "text-slate-500"
                        )}>
                            <p className="text-sm">Nenhum fluxo encontrado</p>
                            <p className="text-xs mt-1">Crie seu primeiro fluxo clicando em "Novo"</p>
                        </div>
                    ) : (
                        flows.map(flow => (
                            <div
                                key={flow.id}
                                onClick={() => setCurrentFlow(flow)}
                                className={cn(
                                    "p-3 rounded-lg cursor-pointer transition-all border",
                                    currentFlow?.id === flow.id
                                        ? isDark
                                            ? "bg-emerald-500/20 border-emerald-500/50"
                                            : "bg-emerald-50 border-emerald-300"
                                        : isDark
                                            ? "bg-white/5 border-white/10 hover:bg-white/10"
                                            : "bg-slate-50 border-slate-200 hover:bg-slate-100"
                                )}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className={cn(
                                        "font-medium text-sm",
                                        isDark ? "text-white" : "text-slate-800"
                                    )}>{flow.name}</span>
                                    <span className={cn(
                                        "text-xs px-2 py-0.5 rounded-full",
                                        flow.is_active
                                            ? "bg-emerald-500/20 text-emerald-400"
                                            : isDark ? "bg-white/10 text-white/50" : "bg-slate-200 text-slate-500"
                                    )}>
                                        {flow.is_active ? 'Ativo' : 'Inativo'}
                                    </span>
                                </div>
                                {flow.description && (
                                    <p className={cn(
                                        "text-xs truncate",
                                        isDark ? "text-white/50" : "text-slate-500"
                                    )}>{flow.description}</p>
                                )}
                                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-white/5">
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleDeleteFlow(flow.id); }}
                                        className={cn(
                                            "p-1.5 rounded transition-colors",
                                            isDark
                                                ? "hover:bg-red-500/20 text-white/50 hover:text-red-400"
                                                : "hover:bg-red-50 text-slate-400 hover:text-red-500"
                                        )}
                                    >
                                        <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Main Canvas */}
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={handleNodesChange}
                    onEdgesChange={handleEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    nodeTypes={nodeTypes}
                    fitView
                    className={isDark ? "react-flow-dark" : ""}
                    style={{ background: isDark ? '#0f172a' : '#f8fafc' }}
                >
                    <Background color={isDark ? "#334155" : "#cbd5e1"} gap={16} />
                    <Controls
                        className={cn(
                            "!bg-opacity-90 !border !rounded-lg !shadow-lg",
                            isDark ? "!bg-slate-800 !border-white/10" : "!bg-white !border-slate-200"
                        )}
                    />
                    <MiniMap
                        nodeColor={(node) => {
                            switch (node.type) {
                                case 'start': return '#10b981';
                                case 'textMessage': return '#3b82f6';
                                case 'mediaMessage': return '#8b5cf6';
                                case 'wait': return '#f59e0b';
                                case 'conditional': return '#ec4899';
                                case 'variable': return '#06b6d4';
                                case 'webhook': return '#6366f1';
                                default: return '#64748b';
                            }
                        }}
                        className={cn(
                            "!bg-opacity-90 !border !rounded-lg",
                            isDark ? "!bg-slate-800 !border-white/10" : "!bg-white !border-slate-200"
                        )}
                    />

                    {/* Top Panel */}
                    <Panel position="top-center">
                        <div className={cn(
                            "flex items-center gap-3 px-4 py-2 rounded-xl border backdrop-blur-sm",
                            isDark
                                ? "bg-slate-800/90 border-white/10"
                                : "bg-white/90 border-slate-200 shadow-lg"
                        )}>
                            <h2 className={cn(
                                "font-semibold",
                                isDark ? "text-white" : "text-slate-800"
                            )}>
                                {currentFlow ? currentFlow.name : 'Selecione um fluxo'}
                            </h2>
                            {currentFlow && (
                                <button
                                    onClick={handleSaveFlow}
                                    className={cn(
                                        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                                        "bg-emerald-500 hover:bg-emerald-600 text-white"
                                    )}
                                >
                                    <Save className="w-4 h-4" />
                                    Salvar
                                </button>
                            )}
                        </div>
                    </Panel>
                </ReactFlow>

                {/* Node Config Panel (appears when node is selected) */}
                {selectedNode && (
                    <div className={cn(
                        "absolute right-72 top-0 bottom-0 w-80 border-l flex flex-col z-10",
                        isDark ? "bg-slate-900 border-white/10" : "bg-white border-slate-200"
                    )}>
                        <div className={cn(
                            "p-4 border-b flex items-center justify-between",
                            isDark ? "border-white/10" : "border-slate-200"
                        )}>
                            <h3 className={cn(
                                "font-semibold",
                                isDark ? "text-white" : "text-slate-800"
                            )}>Configurar Nó</h3>
                            <button
                                onClick={() => setSelectedNodeState(null)}
                                className={cn(
                                    "p-1.5 rounded-lg transition-colors",
                                    isDark ? "hover:bg-white/10 text-white/60" : "hover:bg-slate-100 text-slate-500"
                                )}
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4">
                            <div className={cn(
                                "inline-block px-3 py-1.5 rounded-lg text-sm font-medium mb-4",
                                "bg-emerald-500/20 text-emerald-400"
                            )}>
                                {selectedNode.type}
                            </div>
                            <p className={cn(
                                "text-sm",
                                isDark ? "text-white/60" : "text-slate-600"
                            )}>
                                Configurações do nó selecionado aparecerão aqui.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* Right Panel - Components Toolbar */}
            <div className={cn(
                "w-72 flex-shrink-0 border-l flex flex-col",
                isDark ? "bg-slate-900/50 border-white/10" : "bg-white border-slate-200"
            )}>
                {/* Header */}
                <div className={cn(
                    "p-4 border-b",
                    isDark ? "border-white/10" : "border-slate-200"
                )}>
                    <h2 className={cn(
                        "font-semibold",
                        isDark ? "text-white" : "text-slate-800"
                    )}>Componentes</h2>
                </div>

                {/* Node Categories */}
                <div className="flex-1 overflow-y-auto p-3 space-y-4">
                    {nodeCategories.map(category => (
                        <div key={category.title}>
                            <h3 className={cn(
                                "text-xs font-semibold uppercase tracking-wider mb-2 px-1",
                                isDark ? "text-white/40" : "text-slate-500"
                            )}>{category.title}</h3>
                            <div className="space-y-1">
                                {category.items.map(item => {
                                    const Icon = item.icon;
                                    const colorClasses = {
                                        emerald: isDark ? 'bg-emerald-500/20 text-emerald-400' : 'bg-emerald-100 text-emerald-600',
                                        blue: isDark ? 'bg-blue-500/20 text-blue-400' : 'bg-blue-100 text-blue-600',
                                        purple: isDark ? 'bg-purple-500/20 text-purple-400' : 'bg-purple-100 text-purple-600',
                                        amber: isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-600',
                                        pink: isDark ? 'bg-pink-500/20 text-pink-400' : 'bg-pink-100 text-pink-600',
                                        cyan: isDark ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-100 text-cyan-600',
                                        indigo: isDark ? 'bg-indigo-500/20 text-indigo-400' : 'bg-indigo-100 text-indigo-600',
                                    };
                                    return (
                                        <button
                                            key={item.type}
                                            onClick={() => handleAddNode(item.type)}
                                            className={cn(
                                                "w-full flex items-center gap-3 p-3 rounded-lg transition-all text-left group",
                                                isDark
                                                    ? "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-500/50"
                                                    : "bg-slate-50 hover:bg-slate-100 border border-slate-200 hover:border-emerald-300"
                                            )}
                                        >
                                            <div className={cn(
                                                "p-2 rounded-lg",
                                                colorClasses[item.color]
                                            )}>
                                                <Icon className="w-4 h-4" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <span className={cn(
                                                    "block text-sm font-medium",
                                                    isDark ? "text-white" : "text-slate-800"
                                                )}>{item.label}</span>
                                                <span className={cn(
                                                    "block text-xs truncate",
                                                    isDark ? "text-white/50" : "text-slate-500"
                                                )}>{item.description}</span>
                                            </div>
                                            <ChevronRight className={cn(
                                                "w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity",
                                                isDark ? "text-white/50" : "text-slate-400"
                                            )} />
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className={cn(
                    "p-4 border-t text-center",
                    isDark ? "border-white/10" : "border-slate-200"
                )}>
                    <p className={cn(
                        "text-xs",
                        isDark ? "text-white/40" : "text-slate-500"
                    )}>
                        Arraste os componentes para o canvas ou clique para adicionar
                    </p>
                </div>
            </div>
        </div>
    );
};

export default FlowBuilder;
