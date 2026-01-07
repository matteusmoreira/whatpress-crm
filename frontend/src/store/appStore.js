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

  syncConnection: async (id) => {
    const result = await ConnectionsAPI.syncStatus(id);
    // Atualizar o status no store
    set(state => ({
      connections: state.connections.map(c =>
        c.id === id ? { ...c, status: result.status, phoneNumber: result.phoneNumber || c.phoneNumber } : c
      )
    }));
    return result;
  },

  // Conversations Actions
  fetchConversations: async (tenantId, filters = {}, options = {}) => {
    const silent = options?.silent;
    const limit = typeof options?.limit === 'number' ? options.limit : 200;
    const offset = typeof options?.offset === 'number' ? options.offset : 0;
    if (!silent) set({ conversationsLoading: true, error: null });
    try {
      const conversations = await ConversationsAPI.list(tenantId, filters, { limit, offset });
      set({ conversations, conversationsLoading: false });
    } catch (error) {
      console.error('Error fetching conversations:', error);
      set({ conversationsLoading: false, error: error.message });
    }
  },

  setSelectedConversation: async (conversation) => {
    let resolved = conversation;
    if (typeof conversation === 'string') {
      const existing = (get().conversations || []).find(c => c.id === conversation);
      resolved = existing || null;
    }

    set({ selectedConversation: resolved, messagesLoading: true });
    if (resolved) {
      try {
        await ConversationsAPI.markAsRead(resolved.id);
        const messages = await MessagesAPI.list(resolved.id, { limit: 50, tail: true });
        set(state => ({
          messages,
          messagesLoading: false,
          conversations: state.conversations.map(c =>
            c.id === resolved.id ? { ...c, unreadCount: 0 } : c
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

  deleteConversation: async (conversationId) => {
    await ConversationsAPI.delete(conversationId);
    set(state => {
      const nextSelected = state.selectedConversation?.id === conversationId ? null : state.selectedConversation;
      return {
        conversations: (state.conversations || []).filter(c => c.id !== conversationId),
        selectedConversation: nextSelected,
        messages: nextSelected ? state.messages : [],
        messagesLoading: nextSelected ? state.messagesLoading : false
      };
    });
  },

  clearConversationMessages: async (conversationId) => {
    await ConversationsAPI.clearMessages(conversationId);
    set(state => ({
      conversations: (state.conversations || []).map(c => c.id === conversationId ? { ...c, lastMessageAt: null, lastMessagePreview: '', unreadCount: 0 } : c),
      messages: state.selectedConversation?.id === conversationId ? [] : state.messages
    }));
  },

  // Messages Actions
  fetchMessages: async (conversationId, options = {}) => {
    const silent = options?.silent;
    if (!silent) set({ messagesLoading: true, error: null });
    try {
      const params = {};
      if (options.after) params.after = options.after;
      if (options.before) params.before = options.before;
      if (options.limit) params.limit = options.limit;
      if (options.tail) params.tail = options.tail;

      const nextMessages = await MessagesAPI.list(conversationId, params);

      if (options.append) {
        set(state => {
          const existingById = new Set((state.messages || []).map(m => m.id));
          const merged = [...(state.messages || [])];
          for (const m of nextMessages || []) {
            if (m?.id && !existingById.has(m.id)) merged.push(m);
          }
          return { messages: merged, messagesLoading: false };
        });
      } else {
        set({ messages: nextMessages, messagesLoading: false });
      }

      return nextMessages;
    } catch (error) {
      console.error('Error fetching messages:', error);
      set({ messagesLoading: false, error: error.message });
      return [];
    }
  },

  sendMessage: async (conversationId, content) => {
    const newMessage = await MessagesAPI.send(conversationId, content);
    set(state => {
      const currentMessages = state.messages || [];
      const existingIdx = currentMessages.findIndex(m => m?.id && newMessage?.id && m.id === newMessage.id);

      const nextMessages =
        existingIdx >= 0
          ? currentMessages.map((m, idx) => (idx === existingIdx ? { ...m, ...newMessage } : m))
          : [...currentMessages, newMessage];

      return {
        messages: nextMessages,
        conversations: (state.conversations || []).map(c =>
          c.id === conversationId
            ? { ...c, lastMessageAt: newMessage.timestamp, lastMessagePreview: String(content || '').substring(0, 50) }
            : c
        )
      };
    });
    return newMessage;
  },

  deleteMessage: async (messageId) => {
    const result = await MessagesAPI.delete(messageId);
    const conversationId = result?.conversationId;
    set(state => {
      const nextMessages = (state.messages || []).filter(m => m.id !== messageId);
      if (!conversationId || state.selectedConversation?.id !== conversationId) {
        return { messages: nextMessages };
      }

      const last = nextMessages[nextMessages.length - 1];
      const lastPreview = last?.content ? String(last.content).slice(0, 50) : '';
      const lastAt = last?.timestamp || null;

      return {
        messages: nextMessages,
        conversations: (state.conversations || []).map(c =>
          c.id === conversationId
            ? { ...c, lastMessageAt: lastAt, lastMessagePreview: lastPreview }
            : c
        )
      };
    });
    return result;
  },

  // UI Actions
  toggleSidebar: () => {
    set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
  },

  clearError: () => {
    set({ error: null });
  }
}));
