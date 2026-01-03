import { create } from 'zustand';
import { TenantsRepository, ConnectionsRepository, ConversationsRepository, MessagesRepository } from '../lib/storage';

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

  // Tenants Actions
  fetchTenants: async () => {
    set({ tenantsLoading: true });
    try {
      const tenants = await TenantsRepository.list();
      const stats = await TenantsRepository.getStats();
      set({ tenants, stats, tenantsLoading: false });
    } catch (error) {
      console.error('Error fetching tenants:', error);
      set({ tenantsLoading: false });
    }
  },

  createTenant: async (tenantData) => {
    const newTenant = await TenantsRepository.create(tenantData);
    set(state => ({ tenants: [...state.tenants, newTenant] }));
    return newTenant;
  },

  updateTenant: async (id, updates) => {
    const updatedTenant = await TenantsRepository.update(id, updates);
    set(state => ({
      tenants: state.tenants.map(t => t.id === id ? updatedTenant : t)
    }));
    return updatedTenant;
  },

  deleteTenant: async (id) => {
    await TenantsRepository.delete(id);
    set(state => ({
      tenants: state.tenants.filter(t => t.id !== id)
    }));
  },

  setSelectedTenant: (tenant) => {
    set({ selectedTenant: tenant });
  },

  // Connections Actions
  fetchConnections: async (tenantId) => {
    set({ connectionsLoading: true });
    try {
      const connections = await ConnectionsRepository.list(tenantId);
      set({ connections, connectionsLoading: false });
    } catch (error) {
      console.error('Error fetching connections:', error);
      set({ connectionsLoading: false });
    }
  },

  createConnection: async (connectionData) => {
    const newConnection = await ConnectionsRepository.create(connectionData);
    set(state => ({ connections: [...state.connections, newConnection] }));
    return newConnection;
  },

  testConnection: async (id) => {
    return await ConnectionsRepository.testConnection(id);
  },

  updateConnectionStatus: async (id, status) => {
    const updatedConnection = await ConnectionsRepository.updateStatus(id, status);
    set(state => ({
      connections: state.connections.map(c => c.id === id ? updatedConnection : c)
    }));
    return updatedConnection;
  },

  deleteConnection: async (id) => {
    await ConnectionsRepository.delete(id);
    set(state => ({
      connections: state.connections.filter(c => c.id !== id)
    }));
  },

  // Conversations Actions
  fetchConversations: async (tenantId, filters = {}) => {
    set({ conversationsLoading: true });
    try {
      const conversations = await ConversationsRepository.list(tenantId, filters);
      set({ conversations, conversationsLoading: false });
    } catch (error) {
      console.error('Error fetching conversations:', error);
      set({ conversationsLoading: false });
    }
  },

  setSelectedConversation: async (conversation) => {
    set({ selectedConversation: conversation, messagesLoading: true });
    if (conversation) {
      await ConversationsRepository.markAsRead(conversation.id);
      const messages = await MessagesRepository.list(conversation.id);
      set(state => ({
        messages,
        messagesLoading: false,
        conversations: state.conversations.map(c => 
          c.id === conversation.id ? { ...c, unreadCount: 0 } : c
        )
      }));
    } else {
      set({ messages: [], messagesLoading: false });
    }
  },

  setConversationFilter: (filter) => {
    set({ conversationFilter: filter });
  },

  updateConversationStatus: async (id, status) => {
    const updated = await ConversationsRepository.updateStatus(id, status);
    set(state => ({
      conversations: state.conversations.map(c => c.id === id ? updated : c),
      selectedConversation: state.selectedConversation?.id === id ? updated : state.selectedConversation
    }));
  },

  // Messages Actions
  sendMessage: async (conversationId, content) => {
    const newMessage = await MessagesRepository.send(conversationId, content);
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
  }
}));
