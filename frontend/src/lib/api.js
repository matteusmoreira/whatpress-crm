// API Client for WhatsApp CRM v2
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

  async register(data) {
    const response = await apiClient.post('/auth/register', data);
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

  async getQRCode(id) {
    const response = await apiClient.get(`/connections/${id}/qrcode`);
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
  },

  async assign(id, agentId) {
    const response = await apiClient.post(`/conversations/${id}/assign`, { agent_id: agentId });
    return response.data;
  },

  async unassign(id) {
    const response = await apiClient.post(`/conversations/${id}/unassign`);
    return response.data;
  },

  async addLabel(conversationId, labelId) {
    const response = await apiClient.post(`/conversations/${conversationId}/labels/${labelId}`);
    return response.data;
  },

  async removeLabel(conversationId, labelId) {
    const response = await apiClient.delete(`/conversations/${conversationId}/labels/${labelId}`);
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

// WhatsApp Direct API
export const WhatsAppAPI = {
  async sendMessage(instanceName, phone, message, type = 'text', mediaUrl = null) {
    const response = await apiClient.post('/whatsapp/send', {
      instance_name: instanceName,
      phone,
      message,
      type,
      media_url: mediaUrl
    });
    return response.data;
  },

  async sendTyping(instanceName, phone) {
    const response = await apiClient.post('/whatsapp/typing', null, {
      params: { instance_name: instanceName, phone }
    });
    return response.data;
  }
};

// Quick Replies API
export const QuickRepliesAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/quick-replies', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async create(tenantId, data) {
    const response = await apiClient.post('/quick-replies', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async delete(replyId) {
    const response = await apiClient.delete(`/quick-replies/${replyId}`);
    return response.data;
  }
};

// Labels API
export const LabelsAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/labels', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async create(tenantId, data) {
    const response = await apiClient.post('/labels', data, { params: { tenant_id: tenantId } });
    return response.data;
  }
};

// Agents API
export const AgentsAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/agents', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async getStats(tenantId, agentId) {
    const response = await apiClient.get(`/agents/${agentId}/stats`, { params: { tenant_id: tenantId } });
    return response.data;
  }
};

// Analytics API
export const AnalyticsAPI = {
  async getOverview(tenantId) {
    const response = await apiClient.get('/analytics/overview', { params: { tenant_id: tenantId } });
    return response.data;
  }
};

// Evolution API
export const EvolutionAPI = {
  async listInstances() {
    const response = await apiClient.get('/evolution/instances');
    return response.data;
  },

  async createInstance(name) {
    const response = await apiClient.post('/evolution/instances', null, { params: { name } });
    return response.data;
  }
};

// Upload API
export const UploadAPI = {
  async uploadFile(file, conversationId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('conversation_id', conversationId);
    
    const response = await apiClient.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  },

  async sendMediaMessage(conversationId, mediaType, mediaUrl, mediaName, content = '') {
    const formData = new FormData();
    formData.append('conversation_id', conversationId);
    formData.append('media_type', mediaType);
    formData.append('media_url', mediaUrl);
    formData.append('media_name', mediaName);
    formData.append('content', content);
    
    const response = await apiClient.post('/messages/media', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  }
};

export default apiClient;
