import { createClient } from '@supabase/supabase-js';

const supabaseUrl = 'https://snaqzbibxafbqxlxusdi.supabase.co';
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNuYXF6YmlieGFmYnF4bHh1c2RpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1MTA2NDAsImV4cCI6MjA4MzA4NjY0MH0.gOWKhIbPTPr9qJo7xN9qN696EovHQb7t3-uFYZlAuRw';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  realtime: {
    params: {
      eventsPerSecond: 10
    }
  }
});

// Realtime subscription helpers
export const setRealtimeAuth = async (token) => {
  if (token) {
    await supabase.realtime.setAuth(token);
  }
};

export const subscribeToMessages = (conversationId, callback) => {
  const channel = supabase
    .channel(`messages:${conversationId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'messages',
        filter: `conversation_id=eq.${conversationId}`
      },
      (payload) => {
        const msg = payload.new;
        callback({
          id: msg.id,
          conversationId: msg.conversation_id,
          content: msg.content,
          type: msg.type,
          direction: msg.direction,
          status: msg.status,
          mediaUrl: msg.media_url,
          timestamp: msg.timestamp
        });
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
};

export const subscribeToConversations = (tenantId, callback) => {
  const channel = supabase
    .channel(`conversations:${tenantId}`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'conversations',
        filter: `tenant_id=eq.${tenantId}`
      },
      (payload) => {
        const conv = payload.new || payload.old;
        callback({
          event: payload.eventType,
          conversation: conv ? {
            id: conv.id,
            tenantId: conv.tenant_id,
            connectionId: conv.connection_id,
            contactPhone: conv.contact_phone,
            contactName: conv.contact_name,
            contactAvatar: conv.contact_avatar,
            status: conv.status,
            assignedTo: conv.assigned_to,
            lastMessageAt: conv.last_message_at,
            unreadCount: conv.unread_count,
            lastMessagePreview: conv.last_message_preview,
            labels: conv.labels || [],
            createdAt: conv.created_at
          } : null
        });
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
};

export const subscribeToConnectionStatus = (tenantId, callback) => {
  const channel = supabase
    .channel(`connections:${tenantId}`)
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'connections',
        filter: `tenant_id=eq.${tenantId}`
      },
      (payload) => {
        callback({
          id: payload.new.id,
          status: payload.new.status
        });
      }
    )
    .subscribe();

  return () => {
    supabase.removeChannel(channel);
  };
};

export default supabase;
