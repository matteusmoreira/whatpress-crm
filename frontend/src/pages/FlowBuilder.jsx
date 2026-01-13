import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    applyNodeChanges,
    applyEdgeChanges,
    Panel,
    ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import './FlowBuilder.css';
import { Plus, Save, Trash2, X, MessageSquare, Image, Clock, GitBranch, Variable, Webhook, ChevronRight, Play, Loader2, Search, Copy, Focus, RotateCcw, Pencil } from 'lucide-react';
import useFlowStore from '../store/flowStore';
import { useTheme } from '../context/ThemeContext';
import { cn } from '../lib/utils';
import { toast } from '../components/ui/glass-toaster';
import { createNode, DEFAULT_NODE_DATA, validateFlow } from '../lib/flowTypes';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../components/ui/accordion';
import { Separator } from '../components/ui/separator';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger
} from '../components/ui/alert-dialog';

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

// Inner component that uses ReactFlow hooks
const FlowBuilderInner = () => {
    const { theme } = useTheme();
    const isDark = theme !== 'light';
    const [nodes, setNodes] = useNodesState([]);
    const [edges, setEdges] = useEdgesState([]);
    const [selectedNode, setSelectedNodeState] = useState(null);
    const [rightPanelTab, setRightPanelTab] = useState('components');
    const [componentSearch, setComponentSearch] = useState('');
    const lastSyncRef = useRef({ nodes: [], edges: [] });
    const reactFlowWrapperRef = useRef(null);
    const reactFlowInstanceRef = useRef(null);
    const [nodeConfigDraft, setNodeConfigDraft] = useState({});
    const [isRenamingFlow, setIsRenamingFlow] = useState(false);

    const {
        nodes: storeNodes,
        edges: storeEdges,
        setNodes: setStoreNodes,
        setEdges: setStoreEdges,
        setSelectedNode,
        fetchFlows,
        fetchFlow,
        flows,
        currentFlow,
        flowName,
        setFlowName,
        setCurrentFlow,
        createFlow,
        saveFlow,
        deleteFlow,
        loading,
        saving,
        error,
        clearError
    } = useFlowStore();

    // Fetch flows on mount
    useEffect(() => {
        fetchFlows();
    }, [fetchFlows]);

    useEffect(() => {
        setIsRenamingFlow(false);
    }, [currentFlow?.id]);

    // Sync nodes from store to ReactFlow
    useEffect(() => {
        if (storeNodes && Array.isArray(storeNodes)) {
            // Check if nodes actually changed to avoid infinite loop
            const nodesChanged = JSON.stringify(storeNodes) !== JSON.stringify(lastSyncRef.current.nodes);
            if (nodesChanged) {
                lastSyncRef.current.nodes = storeNodes;
                setNodes(storeNodes);
            }
        }
    }, [storeNodes, setNodes]);

    // Sync edges from store to ReactFlow
    useEffect(() => {
        if (storeEdges && Array.isArray(storeEdges)) {
            // Check if edges actually changed to avoid infinite loop
            const edgesChanged = JSON.stringify(storeEdges) !== JSON.stringify(lastSyncRef.current.edges);
            if (edgesChanged) {
                lastSyncRef.current.edges = storeEdges;
                setEdges(storeEdges);
            }
        }
    }, [storeEdges, setEdges]);

    // Show error toast when error changes
    useEffect(() => {
        if (error) {
            toast.error(error);
            clearError();
        }
    }, [error, clearError]);

    // Handle nodes change from ReactFlow
    const handleNodesChange = useCallback(
        (changes) => {
            setNodes((currentNodes) => {
                const updatedNodes = applyNodeChanges(changes, currentNodes);
                const newlySelected = updatedNodes.find(n => n.selected) || null;
                setSelectedNode(newlySelected);
                setSelectedNodeState(newlySelected);
                setStoreNodes(updatedNodes);
                lastSyncRef.current.nodes = updatedNodes;
                return updatedNodes;
            });
        },
        [setNodes, setStoreNodes, setSelectedNode]
    );

    // Handle edges change from ReactFlow
    const handleEdgesChange = useCallback(
        (changes) => {
            setEdges((currentEdges) => {
                const updatedEdges = applyEdgeChanges(changes, currentEdges);
                setStoreEdges(updatedEdges);
                lastSyncRef.current.edges = updatedEdges;
                return updatedEdges;
            });
        },
        [setEdges, setStoreEdges]
    );

    // Handle new connection
    const onConnect = useCallback(
        (params) => {
            if (!currentFlow) return;
            const newEdge = {
                ...params,
                id: `edge_${params.source}_${params.target}_${Date.now()}`,
                type: 'smoothstep',
                animated: true
            };

            setEdges((eds) => {
                const updated = addEdge(newEdge, eds);
                setStoreEdges(updated);
                lastSyncRef.current.edges = updated;
                return updated;
            });
        },
        [currentFlow, setEdges, setStoreEdges]
    );

    // Handle node click
    const onNodeClick = useCallback((event, node) => {
        event?.stopPropagation?.();
        setNodes((currentNodes) => {
            const updatedNodes = currentNodes.map((n) => ({
                ...n,
                selected: n.id === node.id
            }));
            setStoreNodes(updatedNodes);
            lastSyncRef.current.nodes = updatedNodes;
            return updatedNodes;
        });
        setSelectedNode(node);
        setSelectedNodeState(node);
        setRightPanelTab('config');
    }, [setNodes, setSelectedNode, setStoreNodes]);

    // Handle pane click (deselect)
    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
        setSelectedNodeState(null);
        setNodes((currentNodes) => {
            const updatedNodes = currentNodes.map((n) => ({ ...n, selected: false }));
            setStoreNodes(updatedNodes);
            lastSyncRef.current.nodes = updatedNodes;
            return updatedNodes;
        });
        setRightPanelTab('components');
    }, [setNodes, setSelectedNode, setStoreNodes]);

    useEffect(() => {
        if (!selectedNode) {
            setNodeConfigDraft({});
            return;
        }
        setNodeConfigDraft(selectedNode.data?.config || {});
    }, [selectedNode]);

    // Create new flow
    const handleCreateFlow = async () => {
        const name = `Novo Fluxo ${(flows?.length || 0) + 1}`;
        const start = createNode('start', { x: 250, y: 150 });
        setStoreNodes([start]);
        setStoreEdges([]);
        lastSyncRef.current.nodes = [start];
        lastSyncRef.current.edges = [];
        setNodes([start]);
        setEdges([]);
        const result = await createFlow({ name, description: '' });
        if (result) {
            toast.success('Fluxo criado com sucesso!');
        }
    };

    // Save current flow
    const handleSaveFlow = async () => {
        if (!currentFlow) {
            toast.error('Selecione um fluxo primeiro');
            return;
        }
        const validation = validateFlow(nodes, edges);
        if (!validation.isValid) {
            validation.errors.slice(0, 5).forEach((err) => toast.error(err));
            return;
        }
        const result = await saveFlow();
        if (result) {
            toast.success('Fluxo salvo com sucesso!');
        }
    };

    // Delete flow
    const handleDeleteFlow = async (flowId, e) => {
        e?.stopPropagation();
        const success = await deleteFlow(flowId);
        if (success) {
            toast.success('Fluxo excluído!');
        }
    };

    // Add node to canvas
    const handleAddNode = (type) => {
        if (!currentFlow) {
            toast.error('Selecione ou crie um fluxo primeiro');
            return;
        }

        if (type === 'start' && nodes.some(n => n.type === 'start')) {
            toast.error('O fluxo deve ter apenas um nó de início');
            return;
        }

        const newNode = createNode(type, {
            x: 250 + Math.random() * 100,
            y: 100 + (nodes.length * 100)
        });

        const updatedNodes = [...nodes, newNode];
        setNodes(updatedNodes);
        setStoreNodes(updatedNodes);
        lastSyncRef.current.nodes = updatedNodes;

        toast.success('Componente adicionado!');
    };

    // Select flow from list
    const handleSelectFlow = async (flow) => {
        if (!flow?.id) return;
        const loaded = await fetchFlow(flow.id);
        if (!loaded) {
            setCurrentFlow(flow);
        }
    };

    const handleDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const handleDrop = useCallback((event) => {
        event.preventDefault();
        if (!currentFlow) {
            toast.error('Selecione ou crie um fluxo primeiro');
            return;
        }

        const type = event.dataTransfer.getData('application/reactflow-node-type');
        if (!type) return;

        if (type === 'start' && nodes.some(n => n.type === 'start')) {
            toast.error('O fluxo deve ter apenas um nó de início');
            return;
        }

        const bounds = reactFlowWrapperRef.current?.getBoundingClientRect();
        if (!bounds || !reactFlowInstanceRef.current) return;

        const position = typeof reactFlowInstanceRef.current.screenToFlowPosition === 'function'
            ? reactFlowInstanceRef.current.screenToFlowPosition({
                x: event.clientX,
                y: event.clientY
            })
            : reactFlowInstanceRef.current.project({
                x: event.clientX - bounds.left,
                y: event.clientY - bounds.top
            });

        const newNode = createNode(type, position);
        const updatedNodes = [...nodes, newNode];
        setNodes(updatedNodes);
        setStoreNodes(updatedNodes);
        lastSyncRef.current.nodes = updatedNodes;
    }, [currentFlow, nodes, setNodes, setStoreNodes]);

    const updateSelectedNodeConfig = useCallback((nextConfig) => {
        if (!selectedNode) return;
        const updatedNodes = nodes.map((n) => (
            n.id === selectedNode.id
                ? { ...n, data: { ...(n.data || DEFAULT_NODE_DATA[n.type]), config: nextConfig } }
                : n
        ));
        const updatedSelectedNode = updatedNodes.find(n => n.id === selectedNode.id) || null;
        setNodes(updatedNodes);
        setStoreNodes(updatedNodes);
        lastSyncRef.current.nodes = updatedNodes;
        setSelectedNode(updatedSelectedNode);
        setSelectedNodeState(updatedSelectedNode);
        setNodeConfigDraft(nextConfig);
    }, [nodes, selectedNode, setNodes, setSelectedNode, setStoreNodes]);

    const performDeleteSelectedNode = useCallback(() => {
        if (!selectedNode) return;
        const updatedNodes = nodes.filter(n => n.id !== selectedNode.id);
        const updatedEdges = edges.filter(e => e.source !== selectedNode.id && e.target !== selectedNode.id);
        setNodes(updatedNodes);
        setEdges(updatedEdges);
        setStoreNodes(updatedNodes);
        setStoreEdges(updatedEdges);
        lastSyncRef.current.nodes = updatedNodes;
        lastSyncRef.current.edges = updatedEdges;
        setSelectedNode(null);
        setSelectedNodeState(null);
        toast.success('Nó deletado');
        setRightPanelTab('components');
    }, [edges, nodes, selectedNode, setEdges, setNodes, setSelectedNode, setStoreEdges, setStoreNodes]);

    const resetSelectedNodeConfig = useCallback(() => {
        if (!selectedNode) return;
        const nextConfig = DEFAULT_NODE_DATA[selectedNode.type]?.config || {};
        updateSelectedNodeConfig(nextConfig);
        toast.success('Configuração restaurada');
    }, [selectedNode, updateSelectedNodeConfig]);

    const duplicateSelectedNode = useCallback(() => {
        if (!selectedNode) return;
        const sourceNode = nodes.find(n => n.id === selectedNode.id) || selectedNode;
        const newNode = createNode(sourceNode.type, {
            x: (sourceNode.position?.x || 0) + 40,
            y: (sourceNode.position?.y || 0) + 40
        });
        newNode.data = { ...(sourceNode.data || DEFAULT_NODE_DATA[sourceNode.type]), config: nodeConfigDraft };
        const updatedNodes = [
            ...nodes.map((n) => ({ ...n, selected: false })),
            { ...newNode, selected: true }
        ];
        setNodes(updatedNodes);
        setStoreNodes(updatedNodes);
        lastSyncRef.current.nodes = updatedNodes;
        setSelectedNode(newNode);
        setSelectedNodeState(newNode);
        setRightPanelTab('config');
        toast.success('Nó duplicado');
    }, [nodeConfigDraft, nodes, selectedNode, setNodes, setSelectedNode, setStoreNodes]);

    const focusSelectedNode = useCallback(() => {
        if (!selectedNode) return;
        const nodeToFocus = nodes.find(n => n.id === selectedNode.id) || selectedNode;
        const instance = reactFlowInstanceRef.current;
        if (!instance?.fitView) return;
        try {
            instance.fitView({ nodes: [nodeToFocus], padding: 0.35, duration: 250 });
        } catch {
            try {
                instance.fitView({ padding: 0.35, duration: 250 });
            } catch { }
        }
    }, [nodes, selectedNode]);

    const filteredNodeCategories = useMemo(() => {
        const q = componentSearch.trim().toLowerCase();
        if (!q) return nodeCategories;
        return nodeCategories
            .map((category) => ({
                ...category,
                items: category.items.filter((item) => {
                    const hay = `${item.label} ${item.description} ${item.type}`.toLowerCase();
                    return hay.includes(q);
                })
            }))
            .filter((category) => category.items.length > 0);
    }, [componentSearch]);

    const quickAddItems = useMemo(() => {
        const preferredTypes = ['textMessage', 'wait', 'conditional', 'webhook'];
        const allItems = nodeCategories.flatMap(c => c.items);
        return preferredTypes.map(t => allItems.find(i => i.type === t)).filter(Boolean);
    }, []);

    const renderNodeConfigFields = () => {
        if (!selectedNode) return null;

        switch (selectedNode.type) {
            case 'start':
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Tipo de Gatilho</Label>
                            <Select
                                value={nodeConfigDraft.trigger || 'manual'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, trigger: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="manual">Manual</SelectItem>
                                    <SelectItem value="keyword">Palavra-chave</SelectItem>
                                    <SelectItem value="schedule">Agendado</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {nodeConfigDraft.trigger === 'keyword' && (
                            <div className="space-y-2">
                                <Label>Palavra-chave</Label>
                                <Input
                                    value={nodeConfigDraft.keyword || ''}
                                    onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, keyword: e.target.value })}
                                    placeholder="Digite a palavra-chave"
                                />
                            </div>
                        )}
                    </>
                );
            case 'textMessage':
                return (
                    <div className="space-y-2">
                        <Label>Mensagem</Label>
                        <Textarea
                            value={nodeConfigDraft.message || ''}
                            onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, message: e.target.value })}
                            placeholder="Digite a mensagem..."
                            rows={8}
                        />
                        <p className={cn("text-xs", isDark ? "text-white/40" : "text-slate-500")}>
                            Use variáveis com {'{nome_variavel}'}
                        </p>
                    </div>
                );
            case 'mediaMessage':
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Tipo de Mídia</Label>
                            <Select
                                value={nodeConfigDraft.mediaType || 'image'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, mediaType: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="image">Imagem</SelectItem>
                                    <SelectItem value="video">Vídeo</SelectItem>
                                    <SelectItem value="document">Documento</SelectItem>
                                    <SelectItem value="audio">Áudio</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>URL da Mídia</Label>
                            <Input
                                value={nodeConfigDraft.mediaUrl || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, mediaUrl: e.target.value })}
                                placeholder="https://exemplo.com/imagem.jpg"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Legenda (opcional)</Label>
                            <Textarea
                                value={nodeConfigDraft.caption || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, caption: e.target.value })}
                                placeholder="Digite uma legenda..."
                                rows={4}
                            />
                        </div>
                    </>
                );
            case 'wait':
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Duração</Label>
                            <Input
                                type="number"
                                value={nodeConfigDraft.duration ?? 1}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, duration: parseInt(e.target.value, 10) || 1 })}
                                min="1"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Unidade</Label>
                            <Select
                                value={nodeConfigDraft.unit || 'seconds'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, unit: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="seconds">Segundos</SelectItem>
                                    <SelectItem value="minutes">Minutos</SelectItem>
                                    <SelectItem value="hours">Horas</SelectItem>
                                    <SelectItem value="days">Dias</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </>
                );
            case 'conditional': {
                const condition = nodeConfigDraft.condition || { variable: '', operator: 'equals', value: '' };
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Variável</Label>
                            <Input
                                value={condition.variable || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, condition: { ...condition, variable: e.target.value } })}
                                placeholder="nome_da_variavel"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Operador</Label>
                            <Select
                                value={condition.operator || 'equals'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, condition: { ...condition, operator: value } })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="equals">Igual a</SelectItem>
                                    <SelectItem value="contains">Contém</SelectItem>
                                    <SelectItem value="greater">Maior que</SelectItem>
                                    <SelectItem value="less">Menor que</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>Valor</Label>
                            <Input
                                value={condition.value || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, condition: { ...condition, value: e.target.value } })}
                                placeholder="Valor para comparar"
                            />
                        </div>
                    </>
                );
            }
            case 'variable':
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Ação</Label>
                            <Select
                                value={nodeConfigDraft.action || 'set'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, action: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="set">Definir</SelectItem>
                                    <SelectItem value="get">Obter</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>Nome da Variável</Label>
                            <Input
                                value={nodeConfigDraft.variableName || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, variableName: e.target.value })}
                                placeholder="nome_da_variavel"
                            />
                        </div>

                        {nodeConfigDraft.action !== 'get' && (
                            <div className="space-y-2">
                                <Label>Valor</Label>
                                <Input
                                    value={nodeConfigDraft.value || ''}
                                    onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, value: e.target.value })}
                                    placeholder="Valor da variável"
                                />
                            </div>
                        )}
                    </>
                );
            case 'webhook':
                return (
                    <>
                        <div className="space-y-2">
                            <Label>Método</Label>
                            <Select
                                value={nodeConfigDraft.method || 'POST'}
                                onValueChange={(value) => updateSelectedNodeConfig({ ...nodeConfigDraft, method: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="GET">GET</SelectItem>
                                    <SelectItem value="POST">POST</SelectItem>
                                    <SelectItem value="PUT">PUT</SelectItem>
                                    <SelectItem value="DELETE">DELETE</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label>URL</Label>
                            <Input
                                value={nodeConfigDraft.url || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, url: e.target.value })}
                                placeholder="https://api.exemplo.com/endpoint"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Variável de Resposta (opcional)</Label>
                            <Input
                                value={nodeConfigDraft.responseVariable || ''}
                                onChange={(e) => updateSelectedNodeConfig({ ...nodeConfigDraft, responseVariable: e.target.value })}
                                placeholder="nome_variavel_resposta"
                            />
                        </div>
                    </>
                );
            default:
                return null;
        }
    };

    return (
        <div className="flex flex-col lg:flex-row h-full overflow-hidden min-w-0">
            {/* Left Panel - Flow List */}
            <div className={cn(
                "w-full lg:w-64 flex-shrink-0 flex flex-col border-b lg:border-b-0 lg:border-r max-h-[320px] lg:max-h-none",
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
                        disabled={saving}
                        className={cn(
                            "flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            "bg-emerald-500 hover:bg-emerald-600 text-white",
                            "disabled:opacity-50 disabled:cursor-not-allowed"
                        )}
                    >
                        {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Plus className="w-4 h-4" />
                        )}
                        Novo
                    </button>
                </div>

                {/* Flow List */}
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                    {loading && !flows.length ? (
                        <div className={cn(
                            "text-center py-8 px-4",
                            isDark ? "text-white/50" : "text-slate-500"
                        )}>
                            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
                            <p className="text-sm">Carregando fluxos...</p>
                        </div>
                    ) : (!flows || flows.length === 0) ? (
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
                                onClick={() => handleSelectFlow(flow)}
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
                                        "font-medium text-sm truncate flex-1",
                                        isDark ? "text-white" : "text-slate-800"
                                    )}>{flow.name}</span>
                                    <span className={cn(
                                        "text-xs px-2 py-0.5 rounded-full ml-2",
                                        flow.is_active || flow.isActive
                                            ? "bg-emerald-500/20 text-emerald-400"
                                            : isDark ? "bg-white/10 text-white/50" : "bg-slate-200 text-slate-500"
                                    )}>
                                        {(flow.is_active || flow.isActive) ? 'Ativo' : 'Inativo'}
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
                                        onClick={(e) => handleDeleteFlow(flow.id, e)}
                                        disabled={loading || saving}
                                        className={cn(
                                            "p-1.5 rounded transition-colors",
                                            "disabled:opacity-50",
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
            <div className="flex-1 relative min-w-0 min-h-[360px] lg:min-h-0 p-2 lg:p-3" ref={reactFlowWrapperRef}>
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={handleNodesChange}
                    onEdgesChange={handleEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    nodeTypes={nodeTypes}
                    onInit={(instance) => {
                        reactFlowInstanceRef.current = instance;
                    }}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
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
                    <Panel position="top-left">
                        <div className={cn(
                            "flex items-center gap-3 px-3 py-2 rounded-xl border backdrop-blur-sm",
                            isDark
                                ? "bg-slate-800/90 border-white/10"
                                : "bg-white/90 border-slate-200 shadow-lg"
                        )}>
                            {currentFlow ? (
                                <div className="flex items-center gap-2">
                                    {isRenamingFlow ? (
                                        <Input
                                            value={flowName}
                                            onChange={(e) => setFlowName(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') setIsRenamingFlow(false);
                                                if (e.key === 'Escape') setIsRenamingFlow(false);
                                            }}
                                            onBlur={() => setIsRenamingFlow(false)}
                                            autoFocus
                                            className={cn(
                                                "h-8 w-[220px] text-sm",
                                                isDark ? "bg-white/5 border-white/10 text-white" : "bg-white"
                                            )}
                                        />
                                    ) : (
                                        <h2 className={cn(
                                            "font-semibold text-sm max-w-[220px] truncate",
                                            isDark ? "text-white" : "text-slate-800"
                                        )}>
                                            {flowName || currentFlow.name || 'Sem nome'}
                                        </h2>
                                    )}
                                    <button
                                        onClick={() => setIsRenamingFlow((v) => !v)}
                                        className={cn(
                                            "p-1.5 rounded-lg transition-colors",
                                            isDark ? "hover:bg-white/10 text-white/60 hover:text-white" : "hover:bg-slate-100 text-slate-500 hover:text-slate-800"
                                        )}
                                        title="Renomear fluxo"
                                    >
                                        <Pencil className="w-4 h-4" />
                                    </button>
                                </div>
                            ) : (
                                <h2 className={cn(
                                    "font-semibold text-sm",
                                    isDark ? "text-white" : "text-slate-800"
                                )}>
                                    Selecione um fluxo
                                </h2>
                            )}
                            {currentFlow && (
                                <button
                                    onClick={handleSaveFlow}
                                    disabled={saving}
                                    className={cn(
                                        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                                        "bg-emerald-500 hover:bg-emerald-600 text-white",
                                        "disabled:opacity-50 disabled:cursor-not-allowed"
                                    )}
                                >
                                    {saving ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <Save className="w-4 h-4" />
                                    )}
                                    {saving ? 'Salvando...' : 'Salvar'}
                                </button>
                            )}
                        </div>
                    </Panel>
                </ReactFlow>

                {/* Empty State when no flow selected */}
                {!currentFlow && (
                    <div className={cn(
                        "absolute inset-0 flex items-center justify-center pointer-events-none",
                        isDark ? "bg-slate-900/50" : "bg-slate-50/50"
                    )}>
                        <div className={cn(
                            "text-center p-8 rounded-xl",
                            isDark ? "bg-slate-800/80 text-white/60" : "bg-white/80 text-slate-500"
                        )}>
                            <Play className="w-12 h-12 mx-auto mb-4 opacity-50" />
                            <h3 className="text-lg font-medium mb-2">Nenhum fluxo selecionado</h3>
                            <p className="text-sm">Selecione um fluxo na lista à esquerda ou crie um novo</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Right Panel - Components Toolbar */}
            <div className={cn(
                "w-full lg:w-80 flex-shrink-0 flex flex-col border-t lg:border-t-0 lg:border-l max-h-[45vh] lg:max-h-none",
                isDark ? "bg-slate-900/50 border-white/10" : "bg-white border-slate-200"
            )}>
                {/* Header */}
                <div className={cn(
                    "p-4 border-b",
                    isDark ? "border-white/10" : "border-slate-200"
                )}>
                    <Tabs value={rightPanelTab} onValueChange={setRightPanelTab} className="w-full">
                        <TabsList className="w-full grid grid-cols-2">
                            <TabsTrigger value="components">Componentes</TabsTrigger>
                            <TabsTrigger value="config" disabled={!selectedNode}>Configurar</TabsTrigger>
                        </TabsList>
                    </Tabs>
                </div>

                <Tabs value={rightPanelTab} onValueChange={setRightPanelTab} className="flex-1 flex flex-col">
                    <ScrollArea className="flex-1">
                        <TabsContent value="components" className="m-0">
                            <div className="p-3 space-y-3">
                                <div className={cn(
                                    "relative",
                                    !currentFlow && "opacity-60"
                                )}>
                                    <Search className={cn(
                                        "absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4",
                                        isDark ? "text-white/40" : "text-slate-400"
                                    )} />
                                    <Input
                                        value={componentSearch}
                                        onChange={(e) => setComponentSearch(e.target.value)}
                                        placeholder="Buscar componentes..."
                                        disabled={!currentFlow}
                                        className="pl-9"
                                    />
                                </div>

                                {currentFlow && !componentSearch.trim() && (
                                    <div className="space-y-2">
                                        <div className={cn(
                                            "text-xs font-semibold uppercase tracking-wider px-1",
                                            isDark ? "text-white/40" : "text-slate-500"
                                        )}>
                                            Atalhos
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            {quickAddItems.map((item) => {
                                                const Icon = item.icon;
                                                return (
                                                    <Button
                                                        key={item.type}
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => handleAddNode(item.type)}
                                                        className={cn(
                                                            isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "bg-white"
                                                        )}
                                                    >
                                                        <Icon className="w-4 h-4" />
                                                        {item.label}
                                                    </Button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}

                                {filteredNodeCategories.length === 0 ? (
                                    <div className={cn(
                                        "rounded-xl border p-4 text-center",
                                        isDark ? "border-white/10 bg-white/5 text-white/60" : "border-slate-200 bg-slate-50 text-slate-600"
                                    )}>
                                        <p className="text-sm font-medium">Nenhum componente encontrado</p>
                                        <p className={cn("text-xs mt-1", isDark ? "text-white/40" : "text-slate-500")}>
                                            Tente outro termo de busca.
                                        </p>
                                    </div>
                                ) : (
                                    <Accordion type="multiple" defaultValue={filteredNodeCategories.map(c => c.title)} className="w-full">
                                        {filteredNodeCategories.map(category => (
                                            <AccordionItem key={category.title} value={category.title} className={cn(isDark ? "border-white/10" : "border-slate-200")}>
                                                <AccordionTrigger className={cn(
                                                    "py-3 px-1 text-xs font-semibold uppercase tracking-wider",
                                                    isDark ? "text-white/50 hover:text-white/70" : "text-slate-500 hover:text-slate-700"
                                                )}>
                                                    {category.title}
                                                </AccordionTrigger>
                                                <AccordionContent className="pb-3">
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
                                                                    disabled={!currentFlow}
                                                                    draggable={!!currentFlow}
                                                                    onDragStart={(event) => {
                                                                        event.dataTransfer.setData('application/reactflow-node-type', item.type);
                                                                        event.dataTransfer.effectAllowed = 'move';
                                                                    }}
                                                                    className={cn(
                                                                        "w-full flex items-center gap-3 p-3 rounded-lg transition-all text-left group",
                                                                        "disabled:opacity-50 disabled:cursor-not-allowed",
                                                                        isDark
                                                                            ? "bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-500/40"
                                                                            : "bg-slate-50 hover:bg-slate-100 border border-slate-200 hover:border-emerald-300"
                                                                    )}
                                                                >
                                                                    <div className={cn("p-2 rounded-lg", colorClasses[item.color])}>
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
                                                </AccordionContent>
                                            </AccordionItem>
                                        ))}
                                    </Accordion>
                                )}
                            </div>
                        </TabsContent>

                        <TabsContent value="config" className="m-0">
                            <div className="p-4">
                            {!selectedNode ? (
                                <div className={cn(
                                    "rounded-xl border p-4",
                                    isDark ? "border-white/10 bg-white/5 text-white/60" : "border-slate-200 bg-slate-50 text-slate-600"
                                )}>
                                    <p className="text-sm font-medium">Selecione um nó no canvas</p>
                                    <p className={cn("text-xs mt-1", isDark ? "text-white/40" : "text-slate-500")}>
                                        As configurações aparecem aqui para edição rápida.
                                    </p>
                                </div>
                            ) : (
                                <div className={cn(
                                    "rounded-xl border",
                                    isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"
                                )}>
                                    <div className={cn(
                                        "p-4 border-b",
                                        isDark ? "border-white/10" : "border-slate-200"
                                    )}>
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="min-w-0">
                                                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/20">
                                                    {selectedNode.data?.label || selectedNode.type}
                                                </Badge>
                                                <div className={cn("text-xs mt-2 truncate", isDark ? "text-white/40" : "text-slate-500")}>
                                                    {selectedNode.id}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Button variant="outline" size="icon" onClick={focusSelectedNode}>
                                                    <Focus className="w-4 h-4" />
                                                </Button>
                                                <Button variant="outline" size="icon" onClick={duplicateSelectedNode}>
                                                    <Copy className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        </div>
                                        <div className={cn("text-xs mt-3", isDark ? "text-white/40" : "text-slate-500")}>
                                            Alterações aplicadas automaticamente
                                        </div>
                                    </div>
                                    <div className="p-4 space-y-5">
                                        {renderNodeConfigFields()}
                                    </div>
                                    <div className={cn(
                                        "p-4 border-t space-y-2",
                                        isDark ? "border-white/10" : "border-slate-200"
                                    )}>
                                        <div className="flex gap-2">
                                            <Button variant="outline" className="flex-1" onClick={resetSelectedNodeConfig}>
                                                <RotateCcw className="w-4 h-4" />
                                                Restaurar
                                            </Button>
                                            <Button variant="outline" className="flex-1" onClick={onPaneClick}>
                                                <X className="w-4 h-4" />
                                                Fechar
                                            </Button>
                                        </div>

                                        {currentFlow && (
                                            <Button
                                                onClick={handleSaveFlow}
                                                disabled={saving}
                                                className="w-full"
                                            >
                                                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                                                {saving ? 'Salvando...' : 'Salvar Fluxo'}
                                            </Button>
                                        )}

                                        <Separator className={cn(isDark ? "bg-white/10" : "bg-slate-200")} />

                                        <AlertDialog>
                                            <AlertDialogTrigger asChild>
                                                <Button variant="destructive" className="w-full">
                                                    <Trash2 className="w-4 h-4" />
                                                    Deletar Nó
                                                </Button>
                                            </AlertDialogTrigger>
                                            <AlertDialogContent>
                                                <AlertDialogHeader>
                                                    <AlertDialogTitle>Deletar nó?</AlertDialogTitle>
                                                    <AlertDialogDescription>
                                                        Isso removerá o nó e suas conexões. Esta ação não pode ser desfeita.
                                                    </AlertDialogDescription>
                                                </AlertDialogHeader>
                                                <AlertDialogFooter>
                                                    <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                                    <AlertDialogAction onClick={performDeleteSelectedNode}>Deletar</AlertDialogAction>
                                                </AlertDialogFooter>
                                            </AlertDialogContent>
                                        </AlertDialog>
                                    </div>
                                </div>
                            )}
                        </div>
                        </TabsContent>
                    </ScrollArea>
                </Tabs>

                {/* Footer */}
                <div className={cn(
                    "p-4 border-t text-center",
                    isDark ? "border-white/10" : "border-slate-200"
                )}>
                    <p className={cn(
                        "text-xs",
                        isDark ? "text-white/40" : "text-slate-500"
                    )}>
                        {rightPanelTab === 'config'
                            ? (selectedNode ? "Dica: duplique e centralize pelo topo do painel" : "Selecione um nó para configurar")
                            : (currentFlow ? "Dica: use a busca para encontrar ações rápido" : "Selecione um fluxo para começar")}
                    </p>
                </div>
            </div>
        </div>
    );
};

// Main component wrapped with ReactFlowProvider
const FlowBuilder = () => {
    return (
        <ReactFlowProvider>
            <FlowBuilderInner />
        </ReactFlowProvider>
    );
};

export default FlowBuilder;
