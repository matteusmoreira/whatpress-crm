import { create } from 'zustand';
import { TenantsAPI, ConnectionsAPI, ConversationsAPI, MessagesAPI } from '../lib/api';

export const useAppStore = create((set, get) => ({
  // Tenants State
  tenants: [],
  selectedTenant: null,
  tenantsLoading: false,
  stats: null,

  // Connections State
  connections: [],
  connectionsLoading: false,

  // Conversations State
  conversations: [],
  selectedConversation: null,
  conversationsLoading: false,
  conversationFilter: 'all',

  // Messages State
  messages: [],
  messagesLoading: false,

  // Sidebar State
  sidebarCollapsed: false,

  // Error State
  error: null,

  // Tenants Actions
  fetchTenants: async () => {
    set({ tenantsLoading: true, error: null });
    try {
      const [tenants, stats] = await Promise.all([
        TenantsAPI.list(),
        TenantsAPI.getStats()
      ]);
      set({ tenants, stats, tenantsLoading: false });
    } catch (error) {
      console.error('Error fetching tenants:', error);
      set({ tenantsLoading: false, error: error.message });
    }
  },

  createTenant: async (tenantData) => {
    const newTenant = await TenantsAPI.create(tenantData);
    set(state => ({ tenants: [...state.tenants, newTenant] }));
    return newTenant;
  },

  updateTenant: async (id, updates) => {
    const updatedTenant = await TenantsAPI.update(id, updates);
    set(state => ({
      tenants: state.tenants.map(t => t.id === id ? updatedTenant : t)
    }));
    return updatedTenant;
  },

  deleteTenant: async (id) => {
    await TenantsAPI.delete(id);
    set(state => ({
      tenants: state.tenants.filter(t => t.id !== id)
    }));
  },

  setSelectedTenant: (tenant) => {
    set({ selectedTenant: tenant });
  },

  // Connections Actions
  fetchConnections: async (tenantId) => {
    set({ connectionsLoading: true, error: null });
    try {
      const connections = await ConnectionsAPI.list(tenantId);
      set({ connections, connectionsLoading: false });
    } catch (error) {
      console.error('Error fetching connections:', error);
      set({ connectionsLoading: false, error: error.message });
    }
  },

  createConnection: async (connectionData) => {
    const newConnection = await ConnectionsAPI.create(connectionData);
    set(state => ({ connections: [...state.connections, newConnection] }));
    return newConnection;
  },

  testConnection: async (id) => {
    const result = await ConnectionsAPI.testConnection(id);
    // If connected, update the connection status
    if (result.success && !result.qrcode) {
      set(state => ({
        connections: state.connections.map(c => 
          c.id === id ? { ...c, status: 'connected' } : c
        )
      }));
    }
    return result;
  },

  updateConnectionStatus: async (id, status) => {
    const updatedConnection = await ConnectionsAPI.updateStatus(id, status);
    set(state => ({
      connections: state.connections.map(c => c.id === id ? updatedConnection : c)
    }));
    return updatedConnection;
  },

  deleteConnection: async (id) => {
    await ConnectionsAPI.delete(id);
    set(state => ({
      connections: state.connections.filter(c => c.id !== id)
    }));
  },

  // Conversations Actions
  fetchConversations: async (tenantId, filters = {}) => {
    set({ conversationsLoading: true, error: null });
    try {
      const conversations = await ConversationsAPI.list(tenantId, filters);
      set({ conversations, conversationsLoading: false });
    } catch (error) {
      console.error('Error fetching conversations:', error);
      set({ conversationsLoading: false, error: error.message });
    }
  },

  setSelectedConversation: async (conversation) => {
    set({ selectedConversation: conversation, messagesLoading: true });
    if (conversation) {
      try {
        await ConversationsAPI.markAsRead(conversation.id);
        const messages = await MessagesAPI.list(conversation.id);
        set(state => ({
          messages,
          messagesLoading: false,
          conversations: state.conversations.map(c => 
            c.id === conversation.id ? { ...c, unreadCount: 0 } : c
          )
        }));
      } catch (error) {
        console.error('Error loading messages:', error);
        set({ messagesLoading: false });
      }
    } else {
      set({ messages: [], messagesLoading: false });
    }
  },

  setConversationFilter: (filter) => {
    set({ conversationFilter: filter });
  },

  updateConversationStatus: async (id, status) => {
    const updated = await ConversationsAPI.updateStatus(id, status);
    set(state => ({
      conversations: state.conversations.map(c => c.id === id ? { ...c, status } : c),
      selectedConversation: state.selectedConversation?.id === id 
        ? { ...state.selectedConversation, status } 
        : state.selectedConversation
    }));
  },

  // Messages Actions
  sendMessage: async (conversationId, content) => {
    const newMessage = await MessagesAPI.send(conversationId, content);
    set(state => ({
      messages: [...state.messages, newMessage],
      conversations: state.conversations.map(c => 
        c.id === conversationId 
          ? { ...c, lastMessageAt: newMessage.timestamp, lastMessagePreview: content.substring(0, 50) }
          : c
      )
    }));
    return newMessage;
  },

  // UI Actions
  toggleSidebar: () => {
    set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
  },

  clearError: () => {
    set({ error: null });
  }
}));
