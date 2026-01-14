// API Client for WhatsApp CRM v2
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

const BACKEND_URL = resolveBackendUrl();
const API = `${BACKEND_URL}/api`;

// Create axios instance
const apiClient = axios.create({
  baseURL: API,
  withCredentials: true,
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
      const url = String(error.config?.url || '');
      const isAuthAttempt =
        url.startsWith('/auth/login') ||
        url.startsWith('/auth/register') ||
        url.startsWith('/auth/logout');

      if (!isAuthAttempt) {
        localStorage.removeItem('whatsapp-crm-auth');

        if (typeof window !== 'undefined') {
          window.dispatchEvent(new Event('auth:unauthorized'));
        }
      }
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

  async logout() {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  },

  async register(data) {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
  },

  async getCurrentUser() {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  async updateCurrentUser(data) {
    const response = await apiClient.patch('/auth/me', data);
    return response.data;
  }
};

// Tenants API
export const TenantsAPI = {
  async list() {
    const response = await apiClient.get('/tenants');
    return response.data;
  },

  async getById(id) {
    const response = await apiClient.get(`/tenants/${id}`);
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

// Plans API (SuperAdmin)
export const PlansAPI = {
  async list() {
    const response = await apiClient.get('/plans');
    return response.data;
  },

  async getById(id) {
    const response = await apiClient.get(`/plans/${id}`);
    return response.data;
  },

  async create(data) {
    const response = await apiClient.post('/plans', data);
    return response.data;
  },

  async update(id, data) {
    const response = await apiClient.put(`/plans/${id}`, data);
    return response.data;
  },

  async delete(id) {
    const response = await apiClient.delete(`/plans/${id}`);
    return response.data;
  }
};

// Users API (SuperAdmin)
export const UsersAPI = {
  async list(filters = {}) {
    const response = await apiClient.get('/users', { params: filters });
    return response.data;
  },

  async getById(id) {
    const response = await apiClient.get(`/users/${id}`);
    return response.data;
  },

  async create(data) {
    const response = await apiClient.post('/users', data);
    return response.data;
  },

  async update(id, data) {
    const response = await apiClient.put(`/users/${id}`, data);
    return response.data;
  },

  async delete(id) {
    const response = await apiClient.delete(`/users/${id}`);
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
    // Converter camelCase para snake_case para o backend
    const payload = {
      tenant_id: data.tenantId,
      provider: data.provider,
      instance_name: data.instanceName,
      phone_number: data.phoneNumber || ''
    };
    const response = await apiClient.post('/connections', payload);
    return response.data;
  },

  async testConnection(id) {
    const response = await apiClient.post(`/connections/${id}/test`);
    return response.data;
  },

  async syncStatus(id) {
    const response = await apiClient.post(`/connections/${id}/sync`);
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
  async initiate(phone, contactId = null) {
    const response = await apiClient.post('/conversations/initiate', {
      phone,
      contact_id: contactId
    });
    return response.data;
  },

  async list(tenantId, filters = {}, options = {}) {
    const params = { tenant_id: tenantId, ...filters };
    if (typeof options?.limit === 'number') params.limit = options.limit;
    if (typeof options?.offset === 'number') params.offset = options.offset;
    const response = await apiClient.get('/conversations', { params });
    return response.data;
  },

  async purgeAll(tenantId = null) {
    const params = tenantId ? { tenant_id: tenantId } : undefined;
    const response = await apiClient.delete('/conversations/purge', { params });
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

  async clearMessages(conversationId) {
    const response = await apiClient.delete(`/conversations/${conversationId}/messages`);
    return response.data;
  },

  async delete(conversationId) {
    const response = await apiClient.delete(`/conversations/${conversationId}`);
    return response.data;
  },

  async addLabel(conversationId, labelId) {
    const response = await apiClient.post(`/conversations/${conversationId}/labels/${labelId}`);
    return response.data;
  },

  async removeLabel(conversationId, labelId) {
    const response = await apiClient.delete(`/conversations/${conversationId}/labels/${labelId}`);
    return response.data;
  },

  async transfer(conversationId, toAgentId, reason) {
    const response = await apiClient.post(`/conversations/${conversationId}/transfer`, {
      to_agent_id: toAgentId,
      reason
    });
    return response.data;
  },

  async acceptTransfer(conversationId) {
    const response = await apiClient.post(`/conversations/${conversationId}/transfer/accept`);
    return response.data;
  }
};

export const ContactsAPI = {
  async list(tenantId, search = '', limit = 50, offset = 0) {
    const params = { limit, offset };
    if (tenantId) params.tenant_id = tenantId;
    if (search) params.search = search;
    const response = await apiClient.get('/contacts', { params });
    return response.data;
  },

  async create(tenantId, data) {
    const config = tenantId ? { params: { tenant_id: tenantId } } : undefined;
    const response = await apiClient.post('/contacts', data, config);
    return response.data;
  },

  async getById(contactId) {
    const response = await apiClient.get(`/contacts/${contactId}`);
    return response.data;
  },

  async getByPhone(tenantId, phone) {
    const response = await apiClient.get('/contacts/by-phone', { params: { tenant_id: tenantId, phone } });
    return response.data;
  },

  async update(contactId, data) {
    const response = await apiClient.patch(`/contacts/${contactId}`, data);
    return response.data;
  },

  async delete(contactId) {
    const response = await apiClient.delete(`/contacts/${contactId}`);
    return response.data;
  },

  async purgeAll(tenantId = null) {
    const params = tenantId ? { tenant_id: tenantId } : undefined;
    const response = await apiClient.delete('/contacts/purge', { params });
    return response.data;
  },

  async history(contactId, limit = 20) {
    const response = await apiClient.get(`/contacts/${contactId}/history`, { params: { limit } });
    return response.data;
  }
};

// Messages API
export const MessagesAPI = {
  async list(conversationId, params = {}) {
    const response = await apiClient.get('/messages', { params: { conversation_id: conversationId, ...params } });
    return response.data;
  },

  async send(conversationId, content, type = 'text') {
    const response = await apiClient.post('/messages', {
      conversation_id: conversationId,
      content,
      type
    });
    return response.data;
  },

  async delete(messageId) {
    const response = await apiClient.delete(`/messages/${messageId}`);
    return response.data;
  },

  async getReactions(messageId) {
    const response = await apiClient.get(`/messages/${messageId}/reactions`);
    return response.data;
  },

  async addReaction(messageId, emoji) {
    const response = await apiClient.post(`/messages/${messageId}/reactions`, null, { params: { emoji } });
    return response.data;
  },

  async removeReaction(messageId, reactionId) {
    const response = await apiClient.delete(`/messages/${messageId}/reactions/${reactionId}`);
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

  async update(replyId, data) {
    const response = await apiClient.put(`/quick-replies/${replyId}`, data);
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
  },

  async update(labelId, data) {
    const response = await apiClient.put(`/labels/${labelId}`, data);
    return response.data;
  },

  async delete(labelId) {
    const response = await apiClient.delete(`/labels/${labelId}`);
    return response.data;
  }
};

// Auto Messages API
export const AutoMessagesAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/auto-messages', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async create(tenantId, data) {
    // Converter camelCase para snake_case para o backend
    const payload = {
      type: data.type,
      name: data.name,
      message: data.message,
      trigger_keyword: data.triggerKeyword || null,
      is_active: data.isActive ?? true,
      schedule_start: data.scheduleStart || null,
      schedule_end: data.scheduleEnd || null,
      schedule_days: data.scheduleDays || null,
      delay_seconds: data.delaySeconds || 0
    };
    const response = await apiClient.post('/auto-messages', payload, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async update(messageId, data) {
    // Converter camelCase para snake_case para o backend
    const payload = {
      type: data.type,
      name: data.name,
      message: data.message,
      trigger_keyword: data.triggerKeyword || null,
      is_active: data.isActive ?? true,
      schedule_start: data.scheduleStart || null,
      schedule_end: data.scheduleEnd || null,
      schedule_days: data.scheduleDays || null,
      delay_seconds: data.delaySeconds || 0
    };
    const response = await apiClient.put(`/auto-messages/${messageId}`, payload);
    return response.data;
  },

  async delete(messageId) {
    const response = await apiClient.delete(`/auto-messages/${messageId}`);
    return response.data;
  },

  async toggle(messageId) {
    const response = await apiClient.patch(`/auto-messages/${messageId}/toggle`);
    return response.data;
  }
};

// Webhooks API
export const WebhooksAPI = {
  async list(tenantId) {
    const response = await apiClient.get('/webhooks', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async create(tenantId, data) {
    const response = await apiClient.post('/webhooks', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async update(webhookId, data) {
    const response = await apiClient.put(`/webhooks/${webhookId}`, data);
    return response.data;
  },

  async delete(webhookId) {
    const response = await apiClient.delete(`/webhooks/${webhookId}`);
    return response.data;
  },

  async toggle(webhookId) {
    const response = await apiClient.patch(`/webhooks/${webhookId}/toggle`);
    return response.data;
  }
};

// Templates API
export const TemplatesAPI = {
  async list(tenantId, category = null) {
    const params = { tenant_id: tenantId };
    if (category) params.category = category;
    const response = await apiClient.get('/templates', { params });
    return response.data;
  },

  async create(tenantId, data) {
    const response = await apiClient.post('/templates', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async update(templateId, data) {
    const response = await apiClient.put(`/templates/${templateId}`, data);
    return response.data;
  },

  async delete(templateId) {
    const response = await apiClient.delete(`/templates/${templateId}`);
    return response.data;
  },

  async use(templateId) {
    const response = await apiClient.post(`/templates/${templateId}/use`);
    return response.data;
  }
};

// Knowledge Base API
export const KnowledgeBaseAPI = {
  // Categories
  async listCategories(tenantId) {
    const response = await apiClient.get('/kb/categories', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async createCategory(tenantId, data) {
    const response = await apiClient.post('/kb/categories', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async deleteCategory(categoryId) {
    const response = await apiClient.delete(`/kb/categories/${categoryId}`);
    return response.data;
  },

  // Articles
  async listArticles(tenantId, categoryId = null, publishedOnly = true) {
    const params = { tenant_id: tenantId, published_only: publishedOnly };
    if (categoryId) params.category_id = categoryId;
    const response = await apiClient.get('/kb/articles', { params });
    return response.data;
  },

  async createArticle(tenantId, data) {
    const response = await apiClient.post('/kb/articles', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async updateArticle(articleId, data) {
    const response = await apiClient.put(`/kb/articles/${articleId}`, data);
    return response.data;
  },

  async deleteArticle(articleId) {
    const response = await apiClient.delete(`/kb/articles/${articleId}`);
    return response.data;
  },

  async viewArticle(articleId) {
    const response = await apiClient.post(`/kb/articles/${articleId}/view`);
    return response.data;
  },

  async feedbackArticle(articleId, helpful) {
    const response = await apiClient.post(`/kb/articles/${articleId}/feedback`, null, { params: { helpful } });
    return response.data;
  },

  // FAQs
  async listFaqs(tenantId, categoryId = null) {
    const params = { tenant_id: tenantId };
    if (categoryId) params.category_id = categoryId;
    const response = await apiClient.get('/kb/faqs', { params });
    return response.data;
  },

  async createFaq(tenantId, data) {
    const response = await apiClient.post('/kb/faqs', data, { params: { tenant_id: tenantId } });
    return response.data;
  },

  async deleteFaq(faqId) {
    const response = await apiClient.delete(`/kb/faqs/${faqId}`);
    return response.data;
  },

  // Search
  async search(tenantId, query) {
    const response = await apiClient.get('/kb/search', { params: { tenant_id: tenantId, q: query } });
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
  },

  async heartbeat() {
    const response = await apiClient.post('/agents/heartbeat');
    return response.data;
  },

  async setOffline() {
    const response = await apiClient.post('/agents/offline');
    return response.data;
  },

  async getAssignmentHistory(conversationId) {
    const response = await apiClient.get(`/conversations/${conversationId}/assignment-history`);
    return response.data;
  },

  async assignWithHistory(conversationId, agentId) {
    const response = await apiClient.post(`/conversations/${conversationId}/assign-with-history`, { agent_id: agentId });
    return response.data;
  }
};

// Analytics API
export const AnalyticsAPI = {
  async getOverview(tenantId) {
    const response = await apiClient.get('/analytics/overview', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async getMessagesByDay(tenantId, days = 7) {
    const response = await apiClient.get('/analytics/messages-by-day', { params: { tenant_id: tenantId, days } });
    return response.data;
  },

  async getAgentPerformance(tenantId) {
    const response = await apiClient.get('/analytics/agent-performance', { params: { tenant_id: tenantId } });
    return response.data;
  },

  async getConversationsByStatus(tenantId) {
    const response = await apiClient.get('/analytics/conversations-by-status', { params: { tenant_id: tenantId } });
    return response.data;
  }
};

// Reports API
export const ReportsAPI = {
  getConversationsCsvUrl(tenantId, status = null, dateFrom = null, dateTo = null) {
    const params = new URLSearchParams({ tenant_id: tenantId });
    if (status) params.append('status', status);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    return `${apiClient.defaults.baseURL}/reports/conversations/csv?${params.toString()}`;
  },

  getMessagesCsvUrl(conversationId) {
    return `${apiClient.defaults.baseURL}/reports/messages/csv?conversation_id=${conversationId}`;
  },

  getAgentsCsvUrl(tenantId) {
    return `${apiClient.defaults.baseURL}/reports/agents/csv?tenant_id=${tenantId}`;
  },

  // Helper to download with auth
  async downloadCsv(url, filename) {
    const token = localStorage.getItem('access_token');
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error('Download failed');

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
  }
};

// Evolution API
export const EvolutionAPI = {
  async listInstances(tenantId = null) {
    const params = tenantId ? { tenant_id: tenantId } : {};
    const response = await apiClient.get('/evolution/instances', { params });
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

export const MaintenanceAPI = {
  async get() {
    const response = await apiClient.get('/maintenance');
    return response.data;
  },

  async update(patch) {
    const response = await apiClient.patch('/maintenance', patch);
    return response.data;
  },

  async uploadAttachment(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/maintenance/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  }
};

export const MediaAPI = {
  async proxy({ messageId, remoteJid, instanceName, fromMe = false }) {
    const response = await apiClient.get('/media/proxy', {
      params: {
        message_id: messageId,
        remote_jid: remoteJid,
        instance_name: instanceName,
        from_me: Boolean(fromMe)
      }
    });
    return response.data;
  },

  async logLoad({ url, kind = null, messageId = null, success, error = null, ts = null, extra = null }) {
    const response = await apiClient.post('/media/log', {
      url,
      kind,
      messageId,
      success: Boolean(success),
      error,
      ts,
      extra
    });
    return response.data;
  },

  async inspect({ url }) {
    const response = await apiClient.post('/media/inspect', { url });
    return response.data;
  }
};

export default apiClient;
