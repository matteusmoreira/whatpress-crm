import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { setRealtimeAuth, subscribeToMessages, subscribeToConversations, subscribeToConnectionStatus } from '../lib/supabase';
import { useAuthStore } from '../store/authStore';
import { useAppStore } from '../store/appStore';
import { toast } from '../components/ui/glass-toaster';

const RealtimeContext = createContext();

const NOTIFICATION_PREFS_KEY = 'whatsapp-crm-notification-prefs-v1';
const BEEP_SRC = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdH2Onp+dnpmXk5CNiYaEgX9+fX19fn+Bg4WIioyOkJOVl5mbnZ+goaKjo6OjoqGgnpyamJaUkpCOjIqIhoWDgoF/fn19fX5/gIKEhomLjY+RlJaYmp2foKGio6OjoqKhoJ6cmpmXlZOSkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19fn+AgoSGiYuNj5GUlpibnZ+goaKjo6OioqGfnpyamZeVk5GQjoyKiIaFg4KAf359fX1+f4CChIaJi42PkZSWmJudoKChoqOjo6KioZ+enJqZl5WTkZCOjIqIhoWDgoB/fn19fX5/gIKEhomLjY+RlJaYm52foKGio6OjoqKhn56cmpqXlZORkI6MioiGhYOCgH9+fX19';

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
  const { user, token, isAuthenticated } = useAuthStore();
  const {
    selectedConversation,
  } = useAppStore();

  const [isConnected, setIsConnected] = useState(false);
  const statusesRef = useRef({ conversations: 'CLOSED', connections: 'CLOSED' });
  const audioRef = useRef(null);
  const audioUnlockedRef = useRef(false);
  const lastAlertKeyRef = useRef('');

  const tenantId = user?.tenantId;

  const ensureAudio = useCallback(() => {
    if (typeof window === 'undefined') return null;
    if (audioRef.current) return audioRef.current;
    try {
      audioRef.current = new Audio(BEEP_SRC);
      audioRef.current.volume = 0.3;
      return audioRef.current;
    } catch (e) {
      return null;
    }
  }, []);

  const playSound = useCallback(() => {
    const audio = ensureAudio();
    if (!audio) return;
    try {
      audio.currentTime = 0;
    } catch (e) { }
    Promise.resolve(audio.play()).catch(() => { });
  }, [ensureAudio]);

  const showBrowserNotification = useCallback((title, body) => {
    if (typeof window === 'undefined') return;
    if (!('Notification' in window)) return;
    if (window.Notification.permission !== 'granted') return;
    try {
      const n = new window.Notification(title, { body });
      n.onclick = () => {
        try {
          window.focus();
        } catch (e) { }
      };
    } catch (e) { }
  }, []);

  const maybeAlert = useCallback((conversation, body, scopeKey) => {
    if (!conversation?.id) return;
    const prefs = loadNotificationPrefs();
    const key = `${scopeKey || 'conv'}|${conversation.id}|${conversation.lastMessageAt || ''}|${conversation.lastMessagePreview || ''}|${String(body || '')}`;
    if (lastAlertKeyRef.current === key) return;
    lastAlertKeyRef.current = key;

    const title = conversation?.contactName ? `Mensagem de ${conversation.contactName}` : 'Nova mensagem';
    const messageBody = body ? String(body) : (conversation?.lastMessagePreview ? String(conversation.lastMessagePreview) : '[Mensagem]');

    if (prefs.sound) playSound();
    if (prefs.browserNotifications) showBrowserNotification(title, messageBody);
  }, [playSound, showBrowserNotification]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const unlock = () => {
      if (audioUnlockedRef.current) return;
      const audio = ensureAudio();
      if (!audio) return;
      const prevVolume = audio.volume;
      audio.volume = 0;
      Promise.resolve(audio.play())
        .then(() => {
          try {
            audio.pause();
            audio.currentTime = 0;
          } catch (e) { }
          audio.volume = prevVolume;
          audioUnlockedRef.current = true;
        })
        .catch(() => {
          audio.volume = prevVolume;
        });
    };
    window.addEventListener('pointerdown', unlock, { once: true });
    window.addEventListener('keydown', unlock, { once: true });
    return () => {
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
  }, [ensureAudio]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!tenantId) return;
    const unsub = useAppStore.subscribe((state, prevState) => {
      if (!prevState) return;
      const isHidden = typeof document !== 'undefined' ? !!document.hidden : false;
      const hasFocus = typeof document !== 'undefined' && typeof document.hasFocus === 'function' ? !!document.hasFocus() : true;
      const selectedId = state.selectedConversation?.id || null;

      const prevMessages = prevState.messages || [];
      const nextMessages = state.messages || [];
      if (selectedId && nextMessages.length > prevMessages.length) {
        const last = nextMessages[nextMessages.length - 1];
        if (last?.direction === 'inbound' && (isHidden || !hasFocus)) {
          const conv = (state.conversations || []).find(c => c.id === selectedId) || state.selectedConversation;
          const normalizedType = normalizeMessageType(last?.type);
          const fallback =
            normalizedType === 'audio' ? '[Áudio]' :
              normalizedType === 'image' ? '[Imagem]' :
                normalizedType === 'video' ? '[Vídeo]' :
                  normalizedType === 'document' ? '[Documento]' :
                    normalizedType === 'sticker' ? '[Figurinha]' :
                      '[Mensagem]';
          const raw = typeof last?.content === 'string' ? last.content : '';
          const body = raw.trim() ? raw : fallback;
          maybeAlert(conv, body, 'msg');
        }
      }

      const prevById = new Map((prevState.conversations || []).map(c => [c.id, c]));
      for (const conv of state.conversations || []) {
        if (!conv?.id) continue;
        const prevConv = prevById.get(conv.id);
        const wasUnread = prevConv?.unreadCount || 0;
        const nowUnread = conv?.unreadCount || 0;
        const isSelected = selectedId === conv.id;
        const shouldAlert = (isHidden || !hasFocus || !isSelected);
        if (shouldAlert && nowUnread > wasUnread) {
          const body = conv?.lastMessagePreview ? String(conv.lastMessagePreview) : '[Mensagem]';
          maybeAlert(conv, body, 'unread');
        }
      }
    });
    return () => {
      unsub?.();
    };
  }, [isAuthenticated, tenantId, maybeAlert]);

  // Handle new message from realtime
  const handleNewMessage = useCallback((message) => {
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
      const storeState = useAppStore.getState();

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
            storeState.fetchMessages(conversation.id, { silent: true, after: lastTs, append: true, limit: 50 });
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

        if (token) {
          await setRealtimeAuth(token);
        }

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
  }, [isAuthenticated, tenantId, token, handleConversationUpdate, handleConnectionUpdate]);

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
