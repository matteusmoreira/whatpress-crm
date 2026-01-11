import React, { useCallback, useEffect } from 'react';
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
import useFlowStore from '../store/flowStore';
import FlowListPanel from '../components/FlowBuilder/panels/FlowListPanel';
import NodeToolbar from '../components/FlowBuilder/panels/NodeToolbar';
import NodeConfigPanel from '../components/FlowBuilder/panels/NodeConfigPanel';
import './FlowBuilder.css';

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

const FlowBuilder = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    const {
        nodes: storeNodes,
        edges: storeEdges,
        setNodes: setStoreNodes,
        setEdges: setStoreEdges,
        setSelectedNode,
        fetchFlows,
        currentFlow
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
            // Atualizar o store também
            const updatedNodes = nodes.map(node => {
                const change = changes.find(c => c.id === node.id);
                if (change) {
                    if (change.type === 'position' && change.position) {
                        return { ...node, position: change.position };
                    } else if (change.type === 'select') {
                        if (change.selected) {
                            setSelectedNode(node);
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
    }, [setSelectedNode]);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
    }, [setSelectedNode]);

    return (
        <div className="flow-builder-container">
            {/* Sidebar esquerda - Lista de fluxos */}
            <FlowListPanel />

            {/* Canvas principal */}
            <div className="flow-canvas">
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
                    className="react-flow-dark"
                >
                    <Background color="#334155" gap={16} />
                    <Controls className="react-flow-controls" />
                    <MiniMap
                        nodeColor={(node) => {
                            switch (node.type) {
                                case 'start':
                                    return '#10b981';
                                case 'textMessage':
                                    return '#3b82f6';
                                case 'mediaMessage':
                                    return '#8b5cf6';
                                case 'wait':
                                    return '#f59e0b';
                                case 'conditional':
                                    return '#ec4899';
                                case 'variable':
                                    return '#06b6d4';
                                case 'webhook':
                                    return '#6366f1';
                                default:
                                    return '#64748b';
                            }
                        }}
                        className="react-flow-minimap"
                    />

                    {/* Panel superior com nome do fluxo e ações */}
                    <Panel position="top-center" className="flow-header-panel">
                        <div className="flow-header">
                            <h2 className="flow-title">
                                {currentFlow ? currentFlow.name : 'Novo Fluxo'}
                            </h2>
                        </div>
                    </Panel>
                </ReactFlow>
            </div>

            {/* Toolbar direita - Tipos de nós */}
            <NodeToolbar />

            {/* Painel de configuração */}
            <NodeConfigPanel />
        </div>
    );
};

export default FlowBuilder;
