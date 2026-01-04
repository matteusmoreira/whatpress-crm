// API Client for WhatsApp CRM
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Create axios instance
const apiClient = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Add auth token to requests
apiClient.interceptors.request.use((config) => {
  const authData = localStorage.getItem('whatsapp-crm-auth');
  if (authData) {
    const { state } = JSON.parse(authData);
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`;
    }
  }
  return config;
});

// Handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('whatsapp-crm-auth');
      window.location.href = '/sign-in';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const AuthAPI = {
  async login(email, password) {
    const response = await apiClient.post('/auth/login', { email, password });
    return response.data;
  },

  async getCurrentUser() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  }
};

// Tenants API
export const TenantsAPI = {
  async list() {
    const response = await apiClient.get('/tenants');
    return response.data;
  },

  async getStats() {
    const response = await apiClient.get('/tenants/stats');
    return response.data;
  },

  async create(data) {
    const response = await apiClient.post('/tenants', data);
    return response.data;
  },

  async update(id, data) {
    const response = await apiClient.put(`/tenants/${id}`, data);
    return response.data;
  },

  async delete(id) {
    const response = await apiClient.delete(`/tenants/${id}`);
    return response.data;
  }
};

// Connections API
export const ConnectionsAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/connections', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async create(data) {
    const response = await apiClient.post('/connections', data);
    return response.data;
  },

  async testConnection(id) {
    const response = await apiClient.post(`/connections/${id}/test`);
    return response.data;
  },

  async updateStatus(id, status) {
    const response = await apiClient.patch(`/connections/${id}/status`, { status });
    return response.data;
  },

  async delete(id) {
    const response = await apiClient.delete(`/connections/${id}`);
    return response.data;
  }
};

// Conversations API
export const ConversationsAPI = {
  async list(tenantId, filters = {}) {
    const params = { tenant_id: tenantId, ...filters };
    const response = await apiClient.get('/conversations', { params });
    return response.data;
  },

  async updateStatus(id, status) {
    const response = await apiClient.patch(`/conversations/${id}/status`, { status });
    return response.data;
  },

  async markAsRead(id) {
    const response = await apiClient.post(`/conversations/${id}/read`);
    return response.data;
  }
};

// Messages API
export const MessagesAPI = {
  async list(conversationId) {
    const response = await apiClient.get('/messages', { params: { conversation_id: conversationId } });
    return response.data;
  },

  async send(conversationId, content, type = 'text') {
    const response = await apiClient.post('/messages', {
      conversation_id: conversationId,
      content,
      type
    });
    return response.data;
  }
};

export default apiClient;
