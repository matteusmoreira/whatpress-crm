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

// Helper function to get auth token from localStorage (same pattern as api.js)
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

// Helper function to get tenant ID from localStorage
const getAuthTenantId = () => {
    const authData = localStorage.getItem('whatsapp-crm-auth');
    if (authData) {
        try {
            const { state } = JSON.parse(authData);
            return state?.user?.tenantId || null;
        } catch {
            return null;
        }
    }
    return null;
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
    error: null,

    // Ações do canvas
    setNodes: (nodes) => set({ nodes }),
    setEdges: (edges) => set({ edges }),
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
            set({
                currentFlow: flow,
                flowName: flow.name || '',
                flowDescription: flow.description || '',
                flowStatus: flow.status || 'draft',
                isActive: flow.isActive || false,
                nodes: flow.nodes || [],
                edges: flow.edges || []
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

    // API Actions
    fetchFlows: async () => {
        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            const tenantId = getAuthTenantId();

            const response = await axios.get(`${API_URL}/flows`, {
                headers: { Authorization: `Bearer ${token}` },
                params: { tenant_id: tenantId }
            });

            set({ flows: response.data, loading: false });
        } catch (error) {
            console.error('Error fetching flows:', error);
            set({ error: error.message, loading: false });
        }
    },

    fetchFlow: async (flowId) => {
        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            const response = await axios.get(`${API_URL}/flows/${flowId}`, {
                headers: { Authorization: `Bearer ${token}` }
            });

            get().setCurrentFlow(response.data);
            set({ loading: false });
        } catch (error) {
            console.error('Error fetching flow:', error);
            set({ error: error.message, loading: false });
        }
    },

    createFlow: async (flowData = {}) => {
        const { flowName, flowDescription, nodes, edges, flowStatus } = get();
        const name = flowData.name || flowName;
        const description = flowData.description !== undefined ? flowData.description : flowDescription;

        if (!name.trim()) {
            set({ error: 'Nome do fluxo é obrigatório' });
            return null;
        }

        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            const tenantId = getAuthTenantId();

            const response = await axios.post(
                `${API_URL}/flows`,
                {
                    name,
                    description,
                    nodes,
                    edges,
                    status: flowStatus,
                    tenant_id: tenantId
                },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            get().setCurrentFlow(response.data);
            await get().fetchFlows();
            set({ loading: false });
            return response.data;
        } catch (error) {
            console.error('Error creating flow:', error);
            console.error('Error response:', error.response?.data);
            const errorMessage = error.response?.data?.detail || error.message || 'Erro desconhecido';
            set({ error: errorMessage, loading: false });
            return null;
        }
    },

    updateFlow: async () => {
        const { currentFlow, flowName, flowDescription, nodes, edges, flowStatus, isActive } = get();

        if (!currentFlow?.id) {
            set({ error: 'Nenhum fluxo selecionado' });
            return null;
        }

        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
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
                { headers: { Authorization: `Bearer ${token}` } }
            );

            get().setCurrentFlow(response.data);
            await get().fetchFlows();
            set({ loading: false });
            return response.data;
        } catch (error) {
            console.error('Error updating flow:', error);
            set({ error: error.message, loading: false });
            return null;
        }
    },

    deleteFlow: async (flowId) => {
        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            await axios.delete(`${API_URL}/flows/${flowId}`, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (get().currentFlow?.id === flowId) {
                get().setCurrentFlow(null);
            }

            await get().fetchFlows();
            set({ loading: false });
            return true;
        } catch (error) {
            console.error('Error deleting flow:', error);
            set({ error: error.message, loading: false });
            return false;
        }
    },

    duplicateFlow: async (flowId, newName) => {
        if (!newName.trim()) {
            set({ error: 'Nome do novo fluxo é obrigatório' });
            return null;
        }

        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            const response = await axios.post(
                `${API_URL}/flows/${flowId}/duplicate`,
                { name: newName },
                { headers: { Authorization: `Bearer ${token}` } }
            );

            await get().fetchFlows();
            set({ loading: false });
            return response.data;
        } catch (error) {
            console.error('Error duplicating flow:', error);
            set({ error: error.message, loading: false });
            return null;
        }
    },

    toggleFlow: async (flowId) => {
        set({ loading: true, error: null });
        try {
            const token = getAuthToken();
            const response = await axios.patch(
                `${API_URL}/flows/${flowId}/toggle`,
                {},
                { headers: { Authorization: `Bearer ${token}` } }
            );

            // Atualizar o fluxo atual se for o que foi alterado
            if (get().currentFlow?.id === flowId) {
                set({ isActive: response.data.isActive });
            }

            await get().fetchFlows();
            set({ loading: false });
            return response.data;
        } catch (error) {
            console.error('Error toggling flow:', error);
            set({ error: error.message, loading: false });
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
            isActive: false
        });
    }
}));

export default useFlowStore;
