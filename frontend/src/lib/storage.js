// Fake API Layer with localStorage persistence
import { mockTenants, mockUsers, mockConnections, mockConversations, mockMessages, generateId } from './mock-data';

const STORAGE_KEY = 'whatsapp-crm-data-v1';

// Simulate network delay
const delay = (ms = 300) => new Promise(resolve => setTimeout(resolve, ms));

// Initialize storage with mock data if empty
const initializeStorage = () => {
  const existing = localStorage.getItem(STORAGE_KEY);
  if (!existing) {
    const initialData = {
      tenants: mockTenants,
      users: mockUsers,
      connections: mockConnections,
      conversations: mockConversations,
      messages: mockMessages
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(initialData));
  }
};

const getData = () => {
  initializeStorage();
  return JSON.parse(localStorage.getItem(STORAGE_KEY));
};

const saveData = (data) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

// Auth Repository
export const AuthRepository = {
  async login(email, password) {
    await delay(500);
    const data = getData();
    const user = data.users.find(u => u.email === email && u.password === password);
    if (!user) {
      throw new Error('Credenciais inválidas');
    }
    const { password: _, ...userWithoutPassword } = user;
    return userWithoutPassword;
  },

  async getCurrentUser(userId) {
    await delay(200);
    const data = getData();
    const user = data.users.find(u => u.id === userId);
    if (!user) return null;
    const { password: _, ...userWithoutPassword } = user;
    return userWithoutPassword;
  }
};

// Tenants Repository
export const TenantsRepository = {
  async list() {
    await delay(400);
    const data = getData();
    return data.tenants;
  },

  async get(id) {
    await delay(200);
    const data = getData();
    return data.tenants.find(t => t.id === id) || null;
  },

  async create(tenantData) {
    await delay(600);
    const data = getData();
    const newTenant = {
      id: generateId(),
      ...tenantData,
      status: 'active',
      plan: 'free',
      messagesThisMonth: 0,
      connectionsCount: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    data.tenants.push(newTenant);
    saveData(data);
    return newTenant;
  },

  async update(id, updates) {
    await delay(400);
    const data = getData();
    const index = data.tenants.findIndex(t => t.id === id);
    if (index === -1) throw new Error('Tenant não encontrado');
    data.tenants[index] = { ...data.tenants[index], ...updates, updatedAt: new Date().toISOString() };
    saveData(data);
    return data.tenants[index];
  },

  async delete(id) {
    await delay(400);
    const data = getData();
    data.tenants = data.tenants.filter(t => t.id !== id);
    saveData(data);
    return true;
  },

  async getStats() {
    await delay(300);
    const data = getData();
    const activeTenants = data.tenants.filter(t => t.status === 'active').length;
    const totalMessages = data.tenants.reduce((sum, t) => sum + t.messagesThisMonth, 0);
    const totalConnections = data.connections.filter(c => c.status === 'connected').length;
    return {
      totalTenants: data.tenants.length,
      activeTenants,
      totalMessages,
      totalConnections,
      messagesPerDay: Math.round(totalMessages / 30)
    };
  }
};

// Connections Repository
export const ConnectionsRepository = {
  async list(tenantId) {
    await delay(300);
    const data = getData();
    return data.connections.filter(c => c.tenantId === tenantId);
  },

  async get(id) {
    await delay(200);
    const data = getData();
    return data.connections.find(c => c.id === id) || null;
  },

  async create(connectionData) {
    await delay(800);
    const data = getData();
    const newConnection = {
      id: generateId(),
      ...connectionData,
      status: 'disconnected',
      webhookUrl: '',
      config: {},
      createdAt: new Date().toISOString()
    };
    data.connections.push(newConnection);
    
    // Update tenant connections count
    const tenantIndex = data.tenants.findIndex(t => t.id === connectionData.tenantId);
    if (tenantIndex !== -1) {
      data.tenants[tenantIndex].connectionsCount++;
    }
    
    saveData(data);
    return newConnection;
  },

  async updateStatus(id, status) {
    await delay(500);
    const data = getData();
    const index = data.connections.findIndex(c => c.id === id);
    if (index === -1) throw new Error('Conexão não encontrada');
    data.connections[index].status = status;
    if (status === 'connected') {
      data.connections[index].webhookUrl = `https://api.whatsappcrm.com/webhooks/${data.connections[index].instanceName}`;
    }
    saveData(data);
    return data.connections[index];
  },

  async testConnection(id) {
    await delay(1500);
    // Simulate random success/failure
    const success = Math.random() > 0.3;
    if (!success) throw new Error('Falha ao conectar. Verifique as credenciais.');
    return { success: true, message: 'Conexão estabelecida com sucesso!' };
  },

  async delete(id) {
    await delay(400);
    const data = getData();
    const connection = data.connections.find(c => c.id === id);
    data.connections = data.connections.filter(c => c.id !== id);
    
    // Update tenant connections count
    if (connection) {
      const tenantIndex = data.tenants.findIndex(t => t.id === connection.tenantId);
      if (tenantIndex !== -1 && data.tenants[tenantIndex].connectionsCount > 0) {
        data.tenants[tenantIndex].connectionsCount--;
      }
    }
    
    saveData(data);
    return true;
  }
};

// Conversations Repository
export const ConversationsRepository = {
  async list(tenantId, filters = {}) {
    await delay(400);
    const data = getData();
    let conversations = data.conversations.filter(c => c.tenantId === tenantId);
    
    if (filters.status) {
      conversations = conversations.filter(c => c.status === filters.status);
    }
    if (filters.connectionId) {
      conversations = conversations.filter(c => c.connectionId === filters.connectionId);
    }
    
    // Sort by last message
    conversations.sort((a, b) => new Date(b.lastMessageAt) - new Date(a.lastMessageAt));
    
    return conversations;
  },

  async get(id) {
    await delay(200);
    const data = getData();
    return data.conversations.find(c => c.id === id) || null;
  },

  async updateStatus(id, status) {
    await delay(300);
    const data = getData();
    const index = data.conversations.findIndex(c => c.id === id);
    if (index === -1) throw new Error('Conversa não encontrada');
    data.conversations[index].status = status;
    saveData(data);
    return data.conversations[index];
  },

  async markAsRead(id) {
    await delay(200);
    const data = getData();
    const index = data.conversations.findIndex(c => c.id === id);
    if (index === -1) throw new Error('Conversa não encontrada');
    data.conversations[index].unreadCount = 0;
    saveData(data);
    return data.conversations[index];
  }
};

// Messages Repository
export const MessagesRepository = {
  async list(conversationId) {
    await delay(300);
    const data = getData();
    const messages = data.messages.filter(m => m.conversationId === conversationId);
    messages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    return messages;
  },

  async send(conversationId, content, type = 'text') {
    await delay(400);
    const data = getData();
    
    const newMessage = {
      id: generateId(),
      conversationId,
      content,
      type,
      direction: 'outbound',
      status: 'sent',
      mediaUrl: null,
      timestamp: new Date().toISOString()
    };
    
    data.messages.push(newMessage);
    
    // Update conversation
    const convIndex = data.conversations.findIndex(c => c.id === conversationId);
    if (convIndex !== -1) {
      data.conversations[convIndex].lastMessageAt = newMessage.timestamp;
      data.conversations[convIndex].lastMessagePreview = content.substring(0, 50);
    }
    
    // Update tenant message count
    const conversation = data.conversations[convIndex];
    if (conversation) {
      const tenantIndex = data.tenants.findIndex(t => t.id === conversation.tenantId);
      if (tenantIndex !== -1) {
        data.tenants[tenantIndex].messagesThisMonth++;
      }
    }
    
    saveData(data);
    
    // Simulate delivery after short delay
    setTimeout(() => {
      const currentData = getData();
      const msgIndex = currentData.messages.findIndex(m => m.id === newMessage.id);
      if (msgIndex !== -1) {
        currentData.messages[msgIndex].status = 'delivered';
        saveData(currentData);
      }
    }, 1000);
    
    return newMessage;
  }
};

// Initialize on import
initializeStorage();
