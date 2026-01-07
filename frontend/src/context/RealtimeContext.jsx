import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { subscribeToMessages, subscribeToConversations, subscribeToConnectionStatus, setRealtimeAuth } from '../lib/supabase';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { toast } from '../components/ui/glass-toaster';

const RealtimeContext = createContext();

export const RealtimeProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuthStore();
  const {
    selectedConversation,
  } = useAppStore();

  const [isConnected, setIsConnected] = useState(false);
  const [unsubscribers, setUnsubscribers] = useState([]);

  const tenantId = user?.tenantId;

  // Handle new message from realtime
  const handleNewMessage = useCallback((message) => {
    const fallback =
      message.type === 'audio' ? '[Áudio]' :
        message.type === 'image' ? '[Imagem]' :
          message.type === 'video' ? '[Vídeo]' :
            message.type === 'document' ? '[Documento]' :
              '[Mensagem]';

    const raw = (() => {
      if (typeof message.content === 'string') return message.content;
      if (!message.content || typeof message.content !== 'object') return '';
      const c = message.content;
      if (typeof c.content === 'string') return c.content;
      if (typeof c.text === 'string') return c.text;
      if (typeof c.conversation === 'string') return c.conversation;
      const tm = c.textMessage;
      if (tm && typeof tm === 'object' && typeof tm.text === 'string') return tm.text;
      const etm = c.extendedTextMessage;
      if (etm && typeof etm === 'object' && typeof etm.text === 'string') return etm.text;
      return '';
    })();
    const normalizedContent = raw.trim() ? raw : fallback;
    const preview = normalizedContent.slice(0, 50);
    const normalizedMessage = raw.trim() ? { ...message, content: raw } : message;

    useAppStore.setState(state => {
      const isOpenConversation = state.selectedConversation?.id === message.conversationId;
      const alreadyInMessages = (state.messages || []).some(m => m.id === message.id);
      const nextMessages = isOpenConversation && !alreadyInMessages ? [...(state.messages || []), normalizedMessage] : state.messages;

      const updatedConversations = (state.conversations || []).map(c => {
        if (c.id !== message.conversationId) return c;
        const nextUnread =
          message.direction === 'inbound' && !isOpenConversation
            ? (c.unreadCount || 0) + 1
            : isOpenConversation
              ? 0
              : c.unreadCount;
        return {
          ...c,
          lastMessageAt: message.timestamp || c.lastMessageAt,
          lastMessagePreview: preview,
          unreadCount: nextUnread
        };
      });

      const nextConversations = [...updatedConversations].sort((a, b) => {
        const ta = Date.parse(a?.lastMessageAt || '') || 0;
        const tb = Date.parse(b?.lastMessageAt || '') || 0;
        return tb - ta;
      });

      return { messages: nextMessages, conversations: nextConversations };
    });

    if (message.direction === 'inbound') {
      try {
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp+dnpmXk5CNiYaEgX9+fX19fn+Bg4WIioyOkJOVl5mbnZ+goaKjo6OjoqGgnpyamJaUkpCOjIqIhoWDgoF/fn19fX5/gIKEhomLjY+RlJaYmp2foKGio6OjoqKhoJ6cmpmXlZOSkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19');
        audio.volume = 0.3;
        audio.play().catch(() => { });
      } catch (e) { }
    }
  }, []);

  // Handle conversation updates from realtime
  const handleConversationUpdate = useCallback((data) => {
    const { event, conversation } = data;

    if (event === 'INSERT') {
      // New conversation
      useAppStore.setState(state => ({
        conversations: [conversation, ...state.conversations]
      }));

      toast.info('Nova conversa!', {
        description: `${conversation.contactName} iniciou uma conversa`
      });
    } else if (event === 'UPDATE' && conversation) {
      // Updated conversation
      useAppStore.setState(state => {
        const without = (state.conversations || []).filter(c => c.id !== conversation.id);
        const merged = [conversation, ...without];
        const sorted = merged.sort((a, b) => {
          const ta = Date.parse(a?.lastMessageAt || '') || 0;
          const tb = Date.parse(b?.lastMessageAt || '') || 0;
          return tb - ta;
        });
        return { conversations: sorted };
      });
    } else if (event === 'DELETE' && conversation) {
      // Deleted conversation
      useAppStore.setState(state => ({
        conversations: state.conversations.filter(c => c.id !== conversation.id)
      }));
    }
  }, []);

  // Handle connection status updates
  const handleConnectionUpdate = useCallback((data) => {
    useAppStore.setState(state => ({
      connections: state.connections.map(c =>
        c.id === data.id ? { ...c, status: data.status } : c
      )
    }));

    if (data.status === 'connected') {
      toast.success('WhatsApp conectado!');
    } else if (data.status === 'disconnected') {
      toast.warning('WhatsApp desconectado');
    }
  }, []);

  // Subscribe to realtime updates
  useEffect(() => {
    if (!isAuthenticated) return;

    console.log('[Realtime] Initializing...', { isAuthenticated, tenantId });

    if (!tenantId) {
      console.warn('[Realtime] Missing tenantId, skipping subscription');
      return;
    }

    let unsubConversations;
    let unsubConnections;
    let mounted = true;

    const initRealtime = async () => {
      try {
        // Set auth token for realtime RLS
        const token = useAuthStore.getState().token;
        if (token) {
          console.log('[Realtime] Setting auth token...');
          await setRealtimeAuth(token);
          console.log('[Realtime] Auth token set');
        } else {
          console.warn('[Realtime] No token found in authStore');
        }

        if (!mounted) return;

        // Subscribe to conversations
        console.log('[Realtime] Subscribing to conversations for tenant:', tenantId);
        unsubConversations = subscribeToConversations(tenantId, handleConversationUpdate);

        // Subscribe to connection status
        console.log('[Realtime] Subscribing to connections for tenant:', tenantId);
        unsubConnections = subscribeToConnectionStatus(tenantId, handleConnectionUpdate);

        const newUnsubscribers = [unsubConversations, unsubConnections];
        setUnsubscribers(newUnsubscribers);
        setIsConnected(true);
        console.log('[Realtime] Connected and subscribed');
      } catch (err) {
        console.error('[Realtime] Initialization error:', err);
      }
    };

    initRealtime();

    return () => {
      mounted = false;
      console.log('[Realtime] Cleaning up subscriptions');
      unsubConversations?.();
      unsubConnections?.();
      setIsConnected(false);
    };
  }, [isAuthenticated, tenantId, handleConversationUpdate, handleConnectionUpdate]);

  // Subscribe to messages for selected conversation
  useEffect(() => {
    if (!selectedConversation?.id) return;

    const unsubMessages = subscribeToMessages(selectedConversation.id, handleNewMessage);

    return () => {
      unsubMessages?.();
    };
  }, [selectedConversation?.id, handleNewMessage]);

  return (
    <RealtimeContext.Provider value={{ isConnected }}>
      {children}
    </RealtimeContext.Provider>
  );
};

export const useRealtime = () => {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return context;
};
