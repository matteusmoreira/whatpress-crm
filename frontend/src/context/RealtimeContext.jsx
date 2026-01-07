import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { subscribeToMessages, subscribeToConversations, subscribeToConnectionStatus } from '../lib/supabase';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { toast } from '../components/ui/glass-toaster';

const RealtimeContext = createContext();

const NOTIFICATION_PREFS_KEY = 'whatsapp-crm-notification-prefs-v1';

const loadNotificationPrefs = () => {
  if (typeof window === 'undefined') return { browserNotifications: false, sound: true };
  try {
    const raw = window.localStorage.getItem(NOTIFICATION_PREFS_KEY);
    if (!raw) return { browserNotifications: false, sound: true };
    const parsed = JSON.parse(raw);
    return {
      browserNotifications: !!parsed?.browserNotifications,
      sound: parsed?.sound === false ? false : true
    };
  } catch (e) {
    return { browserNotifications: false, sound: true };
  }
};

const normalizeMessageType = (type) => {
  const raw = String(type || '').trim();
  if (!raw) return 'text';

  let t = raw.toLowerCase();
  t = t.replace(/[_-]/g, '');
  if (t.endsWith('message')) t = t.slice(0, -7);

  if (t === 'text' || t === 'chat' || t === 'extendedtext') return 'text';
  if (t === 'image' || t === 'img' || t === 'photo' || t === 'picture' || t === 'imagem') return 'image';
  if (t === 'video' || t === 'gif') return 'video';
  if (t === 'audio' || t === 'ptt' || t === 'voice' || t === 'voicemessage') return 'audio';
  if (t === 'document' || t === 'file' || t === 'documento') return 'document';
  if (t === 'sticker' || t === 'figurinha') return 'sticker';

  return 'unknown';
};

export const RealtimeProvider = ({ children }) => {
  const { user, isAuthenticated } = useAuthStore();
  const {
    selectedConversation,
  } = useAppStore();

  const [isConnected, setIsConnected] = useState(false);
  const statusesRef = useRef({ conversations: 'CLOSED', connections: 'CLOSED' });

  const tenantId = user?.tenantId;

  // Handle new message from realtime
  const handleNewMessage = useCallback((message) => {
    const prefs = loadNotificationPrefs();
    const isHidden = typeof document !== 'undefined' ? !!document.hidden : false;
    const hasFocus = typeof document !== 'undefined' && typeof document.hasFocus === 'function' ? !!document.hasFocus() : true;

    const normalizedType = normalizeMessageType(message.type);
    const fallback =
      normalizedType === 'audio' ? '[Áudio]' :
        normalizedType === 'image' ? '[Imagem]' :
          normalizedType === 'video' ? '[Vídeo]' :
            normalizedType === 'document' ? '[Documento]' :
              normalizedType === 'sticker' ? '[Figurinha]' :
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

      const conversations = state.conversations || [];
      const idx = conversations.findIndex(c => c.id === message.conversationId);
      if (idx < 0) return { messages: nextMessages };

      const current = conversations[idx];
      const nextUnread =
        message.direction === 'inbound' && !isOpenConversation
          ? (current.unreadCount || 0) + 1
          : isOpenConversation
            ? 0
            : current.unreadCount;

      const updated = {
        ...current,
        lastMessageAt: message.timestamp || current.lastMessageAt,
        lastMessagePreview: preview,
        unreadCount: nextUnread
      };

      const normalizeTs = (v) => Date.parse(v || '') || 0;
      const targetTs = normalizeTs(updated.lastMessageAt);
      const without = [...conversations.slice(0, idx), ...conversations.slice(idx + 1)];
      let inserted = false;
      const nextConversations = [];
      for (const c of without) {
        if (!inserted && targetTs >= normalizeTs(c?.lastMessageAt)) {
          nextConversations.push(updated);
          inserted = true;
        }
        nextConversations.push(c);
      }
      if (!inserted) nextConversations.push(updated);

      return { messages: nextMessages, conversations: nextConversations };
    });

    if (message.direction === 'inbound') {
      const state = useAppStore.getState();
      const isOpenConversation = state.selectedConversation?.id === message.conversationId;
      const shouldAlert = isHidden || !hasFocus || !isOpenConversation;

      if (prefs.sound && shouldAlert) {
        try {
          const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp+dnpmXk5CNiYaEgX9+fX19fn+Bg4WIioyOkJOVl5mbnZ+goaKjo6OjoqGgnpyamJaUkpCOjIqIhoWDgoF/fn19fX5/gIKEhomLjY+RlJaYmp2foKGio6OjoqKhoJ6cmpmXlZOSkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19');
          audio.volume = 0.3;
          audio.play().catch(() => { });
        } catch (e) { }
      }

      if (prefs.browserNotifications && shouldAlert && typeof window !== 'undefined' && 'Notification' in window) {
        try {
          if (window.Notification.permission === 'granted') {
            const conv =
              (useAppStore.getState().conversations || []).find(c => c.id === message.conversationId) || null;
            const title = conv?.contactName ? `Mensagem de ${conv.contactName}` : 'Nova mensagem';
            const body = normalizedContent || '[Mensagem]';
            const n = new window.Notification(title, { body });
            n.onclick = () => {
              try {
                window.focus();
              } catch (e) { }
            };
          }
        } catch (e) { }
      }
    }
  }, []);

  // Handle conversation updates from realtime
  const handleConversationUpdate = useCallback((data) => {
    const { event, conversation } = data;

    if (event === 'INSERT') {
      // New conversation
      useAppStore.setState(state => ({
        conversations: [conversation, ...(state.conversations || [])]
      }));

      toast.info('Nova conversa!', {
        description: `${conversation.contactName} iniciou uma conversa`
      });
    } else if (event === 'UPDATE' && conversation) {
      const prefs = loadNotificationPrefs();
      const isHidden = typeof document !== 'undefined' ? !!document.hidden : false;
      const hasFocus = typeof document !== 'undefined' && typeof document.hasFocus === 'function' ? !!document.hasFocus() : true;
      const storeState = useAppStore.getState();
      const prev = (storeState.conversations || []).find(c => c.id === conversation.id) || null;
      const wasUnread = prev?.unreadCount || 0;
      const nowUnread = conversation?.unreadCount || 0;
      const isSelected = storeState.selectedConversation?.id === conversation.id;
      const shouldAlert = (isHidden || !hasFocus || !isSelected) && nowUnread > wasUnread;

      if (shouldAlert && prefs.sound) {
        try {
          const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp+dnpmXk5CNiYaEgX9+fX19fn+Bg4WIioyOkJOVl5mbnZ+goaKjo6OjoqGgnpyamJaUkpCOjIqIhoWDgoF/fn19fX5/gIKEhomLjY+RlJaYmp2foKGio6OjoqKhoJ6cmpmXlZOSkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19');
          audio.volume = 0.3;
          audio.play().catch(() => { });
        } catch (e) { }
      }

      if (shouldAlert && prefs.browserNotifications && typeof window !== 'undefined' && 'Notification' in window) {
        try {
          if (window.Notification.permission === 'granted') {
            const title = conversation?.contactName ? `Mensagem de ${conversation.contactName}` : 'Nova mensagem';
            const body = conversation?.lastMessagePreview ? String(conversation.lastMessagePreview) : '[Mensagem]';
            const n = new window.Notification(title, { body });
            n.onclick = () => {
              try {
                window.focus();
              } catch (e) { }
            };
          }
        } catch (e) { }
      }

      // Updated conversation
      if (storeState.selectedConversation?.id === conversation.id) {
        const currentMessages = storeState.messages || [];
        const last = currentMessages[currentMessages.length - 1];
        const lastTs = last?.timestamp;

        if (!lastTs) {
          storeState.fetchMessages(conversation.id, { silent: true, tail: true, limit: 50 });
        } else {
          const convTs = Date.parse(conversation.lastMessageAt || '') || 0;
          const msgTs = Date.parse(lastTs || '') || 0;
          if (convTs > msgTs) {
            storeState.fetchMessages(conversation.id, { silent: true, after: lastTs, append: true, limit: 200 });
          }
        }
      }

      useAppStore.setState(state => {
        const normalizeTs = (v) => Date.parse(v || '') || 0;
        const without = (state.conversations || []).filter(c => c.id !== conversation.id);
        const targetTs = normalizeTs(conversation.lastMessageAt);

        let inserted = false;
        const nextConversations = [];
        for (const c of without) {
          if (!inserted && targetTs >= normalizeTs(c?.lastMessageAt)) {
            nextConversations.push(conversation);
            inserted = true;
          }
          nextConversations.push(c);
        }
        if (!inserted) nextConversations.push(conversation);

        const nextSelected =
          state.selectedConversation?.id === conversation.id
            ? { ...state.selectedConversation, ...conversation }
            : state.selectedConversation;

        return { conversations: nextConversations, selectedConversation: nextSelected };
      });
    } else if (event === 'DELETE' && conversation) {
      // Deleted conversation
      useAppStore.setState(state => ({
        conversations: (state.conversations || []).filter(c => c.id !== conversation.id)
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

    if (!tenantId) {
      setIsConnected(false);
      return;
    }

    let unsubConversations;
    let unsubConnections;
    let mounted = true;

    const updateStatus = (key, status) => {
      statusesRef.current = { ...statusesRef.current, [key]: status };
      const nextConnected =
        statusesRef.current.conversations === 'SUBSCRIBED' &&
        statusesRef.current.connections === 'SUBSCRIBED';
      if (mounted) setIsConnected(nextConnected);
    };

    const initRealtime = async () => {
      try {
        if (!mounted) return;

        statusesRef.current = { conversations: 'CLOSED', connections: 'CLOSED' };
        setIsConnected(false);

        unsubConversations = subscribeToConversations(tenantId, handleConversationUpdate, (status) => {
          updateStatus('conversations', status);
        });

        unsubConnections = subscribeToConnectionStatus(tenantId, handleConnectionUpdate, (status) => {
          updateStatus('connections', status);
        });
      } catch (err) {
        setIsConnected(false);
      }
    };

    initRealtime();

    return () => {
      mounted = false;
      unsubConversations?.();
      unsubConnections?.();
      statusesRef.current = { conversations: 'CLOSED', connections: 'CLOSED' };
      setIsConnected(false);
    };
  }, [isAuthenticated, tenantId, handleConversationUpdate, handleConnectionUpdate]);

  // Subscribe to messages for selected conversation
  useEffect(() => {
    const conversationId =
      typeof selectedConversation === 'string'
        ? selectedConversation
        : selectedConversation?.id;
    if (!conversationId) return;

    const unsubMessages = subscribeToMessages(conversationId, handleNewMessage);

    return () => {
      unsubMessages?.();
    };
  }, [selectedConversation, handleNewMessage]);

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
