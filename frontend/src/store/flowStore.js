import { create } from 'zustand';
import axios from 'axios';

const resolveBackendUrl = () => {
    const envUrl = process.env.REACT_APP_BACKEND_URL;
    if (envUrl) return envUrl;

    if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://localhost:8000';
        }
    }

    return 'https://whatpress-crm-production.up.railway.app';
};

const API_URL = `${resolveBackendUrl()}/api`;

// Helper function to get auth token from localStorage
const getAuthToken = () => {
    const authData = localStorage.getItem('whatsapp-crm-auth');
    if (authData) {
        try {
            const { state } = JSON.parse(authData);
            return state?.token || null;
        } catch {
            return null;
        }
    }
    return null;
};

const buildAuthConfig = (token, extra = {}) => ({
    withCredentials: true,
    ...(extra || {}),
    headers: {
        ...((extra || {}).headers || {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
});

// Helper to safely parse JSON fields
const safeParseJson = (value, defaultValue = []) => {
    if (value === null || value === undefined) return defaultValue;
    if (Array.isArray(value) || (typeof value === 'object' && !Array.isArray(value))) return value;
    if (typeof value === 'string') {
        try {
            return JSON.parse(value);
        } catch {
            return defaultValue;
        }
    }
    return defaultValue;
};

const useFlowStore = create((set, get) => ({
    // Estado do canvas
    nodes: [],
    edges: [],
    selectedNode: null,
    selectedEdge: null,

    // Fluxo atual
    currentFlow: null,
    flowName: '',
    flowDescription: '',
    flowStatus: 'draft',
    isActive: false,

    // Lista de fluxos salvos
    flows: [],
    loading: false,
    saving: false,
    error: null,
    initialized: false,

    // Ações do canvas
    setNodes: (nodes) => set({ nodes: safeParseJson(nodes, []) }),
    setEdges: (edges) => set({ edges: safeParseJson(edges, []) }),
    setSelectedNode: (node) => set({ selectedNode: node }),
    setSelectedEdge: (edge) => set({ selectedEdge: edge }),

    addNode: (node) => {
        const nodes = get().nodes;
        set({ nodes: [...nodes, node] });
    },

    updateNode: (nodeId, data) => {
        const nodes = get().nodes;
        set({
            nodes: nodes.map(node =>
                node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node
            )
        });
    },

    deleteNode: (nodeId) => {
        const nodes = get().nodes;
        const edges = get().edges;
        set({
            nodes: nodes.filter(node => node.id !== nodeId),
            edges: edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId),
            selectedNode: null
        });
    },

    // Ações de fluxo
    setCurrentFlow: (flow) => {
        if (flow) {
            const parsedNodes = safeParseJson(flow.nodes, []);
            const parsedEdges = safeParseJson(flow.edges, []);
            set({
                currentFlow: flow,
                flowName: flow.name || '',
                flowDescription: flow.description || '',
                flowStatus: flow.status || 'draft',
                isActive: flow.isActive || flow.is_active || false,
                nodes: parsedNodes,
                edges: parsedEdges
            });
        } else {
            set({
                currentFlow: null,
                flowName: '',
                flowDescription: '',
                flowStatus: 'draft',
                isActive: false,
                nodes: [],
                edges: []
            });
        }
    },

    setFlowName: (name) => set({ flowName: name }),
    setFlowDescription: (description) => set({ flowDescription: description }),
    setFlowStatus: (status) => set({ flowStatus: status }),
    clearError: () => set({ error: null }),

    // API Actions
    fetchFlows: async () => {
        const token = getAuthToken();

        set({ loading: true, error: null });
        try {
            const response = await axios.get(`${API_URL}/flows`, {
                ...buildAuthConfig(token)
            });

            const flows = (response.data || []).map(f => ({
                ...f,
                nodes: safeParseJson(f.nodes, []),
                edges: safeParseJson(f.edges, [])
            }));

            set({ flows, loading: false, initialized: true });
        } catch (error) {
            console.error('Error fetching flows:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao carregar fluxos';
            set({ error: errorMessage, loading: false, initialized: true });
        }
    },

    fetchFlow: async (flowId) => {
        const token = getAuthToken();
        set({ loading: true, error: null });
        try {
            const response = await axios.get(`${API_URL}/flows/${flowId}`, {
                ...buildAuthConfig(token)
            });

            const flow = {
                ...response.data,
                nodes: safeParseJson(response.data.nodes, []),
                edges: safeParseJson(response.data.edges, [])
            };

            get().setCurrentFlow(flow);
            set({ loading: false });
            return flow;
        } catch (error) {
            console.error('Error fetching flow:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao carregar fluxo';
            set({ error: errorMessage, loading: false });
            return null;
        }
    },

    createFlow: async (flowData = {}) => {
        const { flowName, flowDescription, nodes, edges, flowStatus } = get();
        const name = flowData.name || flowName;
        const description = flowData.description !== undefined ? flowData.description : flowDescription;

        if (!name || !name.trim()) {
            set({ error: 'Nome do fluxo é obrigatório' });
            return null;
        }

        const token = getAuthToken();

        set({ saving: true, error: null });
        try {
            const response = await axios.post(
                `${API_URL}/flows`,
                {
                    name: name.trim(),
                    description: description || '',
                    nodes: nodes || [],
                    edges: edges || [],
                    status: flowStatus || 'draft'
                },
                buildAuthConfig(token)
            );

            const newFlow = {
                ...response.data,
                nodes: safeParseJson(response.data.nodes, []),
                edges: safeParseJson(response.data.edges, [])
            };

            get().setCurrentFlow(newFlow);
            await get().fetchFlows();
            set({ saving: false });
            return newFlow;
        } catch (error) {
            console.error('Error creating flow:', error);
            console.error('Error response:', error.response?.data);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao criar fluxo';
            set({ error: errorMessage, saving: false });
            return null;
        }
    },

    updateFlow: async () => {
        const { currentFlow, flowName, flowDescription, nodes, edges, flowStatus, isActive } = get();

        if (!currentFlow?.id) {
            set({ error: 'Nenhum fluxo selecionado' });
            return null;
        }

        const token = getAuthToken();
        set({ saving: true, error: null });
        try {
            const response = await axios.put(
                `${API_URL}/flows/${currentFlow.id}`,
                {
                    name: flowName,
                    description: flowDescription,
                    nodes,
                    edges,
                    status: flowStatus,
                    is_active: isActive
                },
                buildAuthConfig(token)
            );

            const updatedFlow = {
                ...response.data,
                nodes: safeParseJson(response.data.nodes, []),
                edges: safeParseJson(response.data.edges, [])
            };

            get().setCurrentFlow(updatedFlow);
            await get().fetchFlows();
            set({ saving: false });
            return updatedFlow;
        } catch (error) {
            console.error('Error updating flow:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao atualizar fluxo';
            set({ error: errorMessage, saving: false });
            return null;
        }
    },

    deleteFlow: async (flowId) => {
        const token = getAuthToken();
        set({ loading: true, error: null });
        try {
            await axios.delete(`${API_URL}/flows/${flowId}`, {
                ...buildAuthConfig(token)
            });

            if (get().currentFlow?.id === flowId) {
                get().setCurrentFlow(null);
            }

            await get().fetchFlows();
            set({ loading: false });
            return true;
        } catch (error) {
            console.error('Error deleting flow:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao deletar fluxo';
            set({ error: errorMessage, loading: false });
            return false;
        }
    },

    duplicateFlow: async (flowId, newName) => {
        if (!newName || !newName.trim()) {
            set({ error: 'Nome do novo fluxo é obrigatório' });
            return null;
        }

        const token = getAuthToken();
        set({ saving: true, error: null });
        try {
            const response = await axios.post(
                `${API_URL}/flows/${flowId}/duplicate`,
                { name: newName.trim() },
                buildAuthConfig(token)
            );

            await get().fetchFlows();
            set({ saving: false });
            return response.data;
        } catch (error) {
            console.error('Error duplicating flow:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao duplicar fluxo';
            set({ error: errorMessage, saving: false });
            return null;
        }
    },

    toggleFlow: async (flowId) => {
        const token = getAuthToken();
        set({ saving: true, error: null });
        try {
            const response = await axios.patch(
                `${API_URL}/flows/${flowId}/toggle`,
                {},
                buildAuthConfig(token)
            );

            const nextActive = !!(response.data?.isActive ?? response.data?.is_active ?? response.data?.active);
            if (get().currentFlow?.id === flowId) {
                const current = get().currentFlow;
                set({
                    isActive: nextActive,
                    currentFlow: current ? { ...current, isActive: nextActive, is_active: nextActive } : current
                });
            }

            await get().fetchFlows();
            set({ saving: false });
            return response.data;
        } catch (error) {
            console.error('Error toggling flow:', error);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro ao alternar fluxo';
            set({ error: errorMessage, saving: false });
            return null;
        }
    },

    // Nova ação para salvar (criar ou atualizar)
    saveFlow: async () => {
        const { currentFlow } = get();
        if (currentFlow?.id) {
            return await get().updateFlow();
        } else {
            return await get().createFlow();
        }
    },

    // Limpar canvas
    clearCanvas: () => {
        set({
            nodes: [],
            edges: [],
            selectedNode: null,
            selectedEdge: null,
            currentFlow: null,
            flowName: '',
            flowDescription: '',
            flowStatus: 'draft',
            isActive: false,
            error: null
        });
    },

    // Reset store
    reset: () => {
        set({
            nodes: [],
            edges: [],
            selectedNode: null,
            selectedEdge: null,
            currentFlow: null,
            flowName: '',
            flowDescription: '',
            flowStatus: 'draft',
            isActive: false,
            flows: [],
            loading: false,
            saving: false,
            error: null,
            initialized: false
        });
    }
}));

export default useFlowStore;
