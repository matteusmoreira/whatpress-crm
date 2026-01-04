import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Search,
  Filter,
  Send,
  Paperclip,
  Smile,
  MoreVertical,
  Phone,
  Check,
  CheckCheck,
  Clock,
  Circle,
  MessageSquare,
  Zap,
  Tag,
  User,
  Users,
  X,
  Image,
  FileText,
  Mic,
  Video,
  Wifi,
  WifiOff
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { useAuthStore } from '../store/authStore';
import { useRealtime } from '../context/RealtimeContext';
import { cn } from '../lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from '../components/ui/glass-toaster';
import FileUpload from '../components/FileUpload';
import QuickRepliesPanel from '../components/QuickRepliesPanel';
import { AgentsAPI, LabelsAPI, ConversationsAPI } from '../lib/api';

// Default labels
const DEFAULT_LABELS = [
  { id: 'urgent', name: 'Urgente', color: '#EF4444' },
  { id: 'vip', name: 'VIP', color: '#F59E0B' },
  { id: 'new', name: 'Novo Cliente', color: '#10B981' },
  { id: 'followup', name: 'Follow-up', color: '#3B82F6' },
  { id: 'complaint', name: 'Reclamação', color: '#EF4444' },
  { id: 'sale', name: 'Venda', color: '#8B5CF6' }
];

const Inbox = () => {
  const { user } = useAuthStore();
  const { isConnected: realtimeConnected } = useRealtime();
  const {
    conversations,
    selectedConversation,
    messages,
    connections,
    conversationsLoading,
    messagesLoading,
    conversationFilter,
    fetchConversations,
    fetchConnections,
    setSelectedConversation,
    setConversationFilter,
    sendMessage,
    updateConversationStatus
  } = useAppStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [newMessage, setNewMessage] = useState('');
  const [selectedConnectionFilter, setSelectedConnectionFilter] = useState('all');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(false);
  const [showLabelsMenu, setShowLabelsMenu] = useState(false);
  const [showAssignMenu, setShowAssignMenu] = useState(false);
  const [agents, setAgents] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const tenantId = user?.tenantId || 'tenant-1';

  // Load agents for assignment
  const loadAgents = useCallback(async () => {
    try {
      const data = await AgentsAPI.list(tenantId);
      setAgents(data);
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  }, [tenantId]);

  // Fetch initial data
  useEffect(() => {
    fetchConversations(tenantId);
    fetchConnections(tenantId);
    loadAgents();
  }, [tenantId, fetchConversations, fetchConnections, loadAgents]);

  // Subscribe to realtime updates
  useEffect(() => {
    if (!tenantId) return;

    const unsubConversations = subscribeToConversations(tenantId, (data) => {
      if (data.event === 'INSERT') {
        useAppStore.setState(state => ({
          conversations: [data.conversation, ...state.conversations.filter(c => c.id !== data.conversation.id)]
        }));
        toast.info('Nova conversa!', { description: `${data.conversation.contactName}` });
      } else if (data.event === 'UPDATE') {
        useAppStore.setState(state => ({
          conversations: state.conversations.map(c => 
            c.id === data.conversation.id ? data.conversation : c
          )
        }));
      }
    });

    setRealtimeConnected(true);

    return () => {
      unsubConversations?.();
      setRealtimeConnected(false);
    };
  }, [tenantId]);

  // Subscribe to messages for selected conversation
  useEffect(() => {
    if (!selectedConversation?.id) return;

    const unsubMessages = subscribeToMessages(selectedConversation.id, (message) => {
      useAppStore.setState(state => {
        const exists = state.messages.some(m => m.id === message.id);
        if (exists) return state;
        return { messages: [...state.messages, message] };
      });

      // Play sound for inbound messages
      if (message.direction === 'inbound') {
        try {
          const audio = new Audio('data:audio/wav;base64,UklGRl9vT19teleXh2dGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU');
          audio.volume = 0.2;
          audio.play().catch(() => {});
        } catch (e) {}
      }
    });

    return () => unsubMessages?.();
  }, [selectedConversation?.id]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setShowQuickReplies(false);
        setShowFileUpload(false);
        setShowLabelsMenu(false);
        setShowAssignMenu(false);
      }
      if (e.key === '/' && e.ctrlKey) {
        e.preventDefault();
        setShowQuickReplies(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const filteredConversations = conversations.filter(conv => {
    const matchesSearch = conv.contactName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.contactPhone.includes(searchQuery);
    const matchesStatus = conversationFilter === 'all' || conv.status === conversationFilter;
    const matchesConnection = selectedConnectionFilter === 'all' || conv.connectionId === selectedConnectionFilter;
    return matchesSearch && matchesStatus && matchesConnection;
  });

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!newMessage.trim() || !selectedConversation) return;

    try {
      await sendMessage(selectedConversation.id, newMessage);
      setNewMessage('');
      inputRef.current?.focus();
    } catch (error) {
      toast.error('Erro ao enviar mensagem');
    }
  };

  const handleFileUpload = async (fileData) => {
    try {
      // For now, send the file info as a message
      await sendMessage(selectedConversation.id, `📎 ${fileData.name}`, fileData.type);
      setShowFileUpload(false);
      toast.success('Arquivo enviado!');
    } catch (error) {
      toast.error('Erro ao enviar arquivo');
    }
  };

  const handleQuickReplySelect = (content) => {
    setNewMessage(content);
    inputRef.current?.focus();
  };

  const handleAssign = async (agentId) => {
    try {
      await ConversationsAPI.assign(selectedConversation.id, agentId);
      const agent = agents.find(a => a.id === agentId);
      toast.success('Conversa atribuída', { description: `Para ${agent?.name}` });
      setShowAssignMenu(false);
    } catch (error) {
      toast.error('Erro ao atribuir conversa');
    }
  };

  const handleAddLabel = async (labelId) => {
    try {
      await ConversationsAPI.addLabel(selectedConversation.id, labelId);
      toast.success('Label adicionada');
      setShowLabelsMenu(false);
    } catch (error) {
      toast.error('Erro ao adicionar label');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'sent': return <Check className="w-4 h-4 text-white/50" />;
      case 'delivered': return <CheckCheck className="w-4 h-4 text-white/50" />;
      case 'read': return <CheckCheck className="w-4 h-4 text-emerald-400" />;
      case 'failed': return <Clock className="w-4 h-4 text-red-400" />;
      default: return null;
    }
  };

  const getConversationStatusColor = (status) => {
    switch (status) {
      case 'open': return 'bg-emerald-500';
      case 'pending': return 'bg-amber-500';
      case 'resolved': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getMessageTypeIcon = (type) => {
    switch (type) {
      case 'image': return <Image className="w-4 h-4" />;
      case 'video': return <Video className="w-4 h-4" />;
      case 'audio': return <Mic className="w-4 h-4" />;
      case 'document': return <FileText className="w-4 h-4" />;
      default: return null;
    }
  };

  const formatTime = (timestamp) => {
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ptBR });
    } catch {
      return '';
    }
  };

  return (
    <div className="h-screen flex flex-col lg:flex-row">
      {/* Conversations List */}
      <div className="w-full lg:w-96 border-r border-white/10 flex flex-col bg-black/20">
        {/* Header */}
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-bold text-white">Conversas</h1>
            {/* Realtime indicator */}
            <div className={cn(
              'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs',
              realtimeConnected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
            )}>
              {realtimeConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {realtimeConnected ? 'Ao vivo' : 'Offline'}
            </div>
          </div>
          
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <GlassInput
              type="text"
              placeholder="Buscar conversas..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 py-2 text-sm"
            />
          </div>

          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            {['all', 'open', 'pending', 'resolved'].map((filter) => (
              <button
                key={filter}
                onClick={() => setConversationFilter(filter)}
                className={cn(
                  'px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                  conversationFilter === filter
                    ? 'bg-emerald-500 text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                )}
              >
                {filter === 'all' ? 'Todas' : filter === 'open' ? 'Abertas' : filter === 'pending' ? 'Pendentes' : 'Resolvidas'}
              </button>
            ))}
          </div>
        </div>

        {/* Connection filter */}
        <div className="p-3 border-b border-white/10">
          <select
            value={selectedConnectionFilter}
            onChange={(e) => setSelectedConnectionFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas as conexões</option>
            {connections.map(conn => (
              <option key={conn.id} value={conn.id} className="bg-emerald-900">
                {conn.phoneNumber}
              </option>
            ))}
          </select>
        </div>

        {/* Conversations */}
        <div className="flex-1 overflow-y-auto">
          {conversationsLoading ? (
            <div className="flex items-center justify-center p-8">
              <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-white/50">
              <MessageSquare className="w-12 h-12 mb-3" />
              <p>Nenhuma conversa encontrada</p>
            </div>
          ) : (
            filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => setSelectedConversation(conv)}
                className={cn(
                  'p-4 border-b border-white/5 cursor-pointer transition-all',
                  'hover:bg-white/5',
                  selectedConversation?.id === conv.id && 'bg-emerald-500/20 border-l-4 border-l-emerald-500'
                )}
              >
                <div className="flex items-start gap-3">
                  <div className="relative">
                    <img
                      src={conv.contactAvatar}
                      alt={conv.contactName}
                      className="w-12 h-12 rounded-full"
                    />
                    <div className={cn(
                      'absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full border-2 border-emerald-900',
                      getConversationStatusColor(conv.status)
                    )} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-white font-medium truncate">{conv.contactName}</span>
                      <span className="text-white/40 text-xs">{formatTime(conv.lastMessageAt)}</span>
                    </div>
                    <p className="text-white/50 text-sm truncate">{conv.lastMessagePreview}</p>
                    <p className="text-white/30 text-xs mt-1">{conv.contactPhone}</p>
                  </div>
                  {conv.unreadCount > 0 && (
                    <span className="bg-emerald-500 text-white text-xs font-bold px-2 py-1 rounded-full min-w-[24px] text-center animate-pulse">
                      {conv.unreadCount}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col bg-gradient-to-br from-emerald-950/50 to-teal-950/50">
        {selectedConversation ? (
          <>
            {/* Chat Header */}
            <div className="p-4 border-b border-white/10 backdrop-blur-sm bg-black/20">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <img
                    src={selectedConversation.contactAvatar}
                    alt={selectedConversation.contactName}
                    className="w-10 h-10 rounded-full"
                  />
                  <div>
                    <h2 className="text-white font-medium">{selectedConversation.contactName}</h2>
                    <p className="text-white/50 text-sm">{selectedConversation.contactPhone}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {/* Status select */}
                  <select
                    value={selectedConversation.status}
                    onChange={(e) => updateConversationStatus(selectedConversation.id, e.target.value)}
                    className="px-3 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none"
                  >
                    <option value="open" className="bg-emerald-900">Aberta</option>
                    <option value="pending" className="bg-emerald-900">Pendente</option>
                    <option value="resolved" className="bg-emerald-900">Resolvida</option>
                  </select>

                  {/* Assign button */}
                  <div className="relative">
                    <button 
                      onClick={() => setShowAssignMenu(!showAssignMenu)}
                      className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                      title="Atribuir"
                    >
                      <Users className="w-5 h-5" />
                    </button>
                    {showAssignMenu && (
                      <div className="absolute right-0 top-full mt-2 w-48 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                        <div className="p-2">
                          <p className="text-white/50 text-xs px-2 mb-2">Atribuir para:</p>
                          {agents.map(agent => (
                            <button
                              key={agent.id}
                              onClick={() => handleAssign(agent.id)}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <img src={agent.avatar} alt={agent.name} className="w-6 h-6 rounded-full" />
                              {agent.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Labels button */}
                  <div className="relative">
                    <button 
                      onClick={() => setShowLabelsMenu(!showLabelsMenu)}
                      className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                      title="Labels"
                    >
                      <Tag className="w-5 h-5" />
                    </button>
                    {showLabelsMenu && (
                      <div className="absolute right-0 top-full mt-2 w-48 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                        <div className="p-2">
                          <p className="text-white/50 text-xs px-2 mb-2">Adicionar label:</p>
                          {DEFAULT_LABELS.map(label => (
                            <button
                              key={label.id}
                              onClick={() => handleAddLabel(label.id)}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: label.color }} />
                              {label.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <button className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors">
                    <Phone className="w-5 h-5" />
                  </button>
                  <button className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors">
                    <MoreVertical className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messagesLoading ? (
                <div className="flex items-center justify-center h-full">
                  <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn(
                        'flex',
                        msg.direction === 'outbound' ? 'justify-end' : 'justify-start'
                      )}
                    >
                      <div
                        className={cn(
                          'max-w-[70%] rounded-2xl px-4 py-3',
                          msg.direction === 'outbound'
                            ? 'bg-emerald-500 text-white rounded-br-md'
                            : 'bg-white/10 backdrop-blur-sm text-white rounded-bl-md'
                        )}
                      >
                        {/* Media type indicator */}
                        {msg.type !== 'text' && (
                          <div className="flex items-center gap-2 mb-2 opacity-70">
                            {getMessageTypeIcon(msg.type)}
                            <span className="text-xs capitalize">{msg.type}</span>
                          </div>
                        )}
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                        <div className={cn(
                          'flex items-center justify-end gap-1 mt-1',
                          msg.direction === 'outbound' ? 'text-white/70' : 'text-white/40'
                        )}>
                          <span className="text-xs">
                            {new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                          {msg.direction === 'outbound' && getStatusIcon(msg.status)}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </>
              )}
            </div>

            {/* File Upload Panel */}
            {showFileUpload && (
              <div className="p-4 border-t border-white/10">
                <FileUpload
                  onUpload={handleFileUpload}
                  onCancel={() => setShowFileUpload(false)}
                />
              </div>
            )}

            {/* Input */}
            <div className="p-4 border-t border-white/10 backdrop-blur-sm bg-black/20 relative">
              {/* Quick Replies Panel */}
              {showQuickReplies && (
                <QuickRepliesPanel
                  onSelect={handleQuickReplySelect}
                  onClose={() => setShowQuickReplies(false)}
                />
              )}

              <form onSubmit={handleSendMessage} className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowFileUpload(!showFileUpload)}
                  className={cn(
                    'p-2 rounded-lg transition-colors',
                    showFileUpload 
                      ? 'bg-emerald-500 text-white' 
                      : 'hover:bg-white/10 text-white/60 hover:text-white'
                  )}
                >
                  <Paperclip className="w-5 h-5" />
                </button>
                <button
                  type="button"
                  onClick={() => setShowQuickReplies(!showQuickReplies)}
                  className={cn(
                    'p-2 rounded-lg transition-colors',
                    showQuickReplies 
                      ? 'bg-emerald-500 text-white' 
                      : 'hover:bg-white/10 text-white/60 hover:text-white'
                  )}
                  title="Respostas rápidas (Ctrl+/)"
                >
                  <Zap className="w-5 h-5" />
                </button>
                <div className="flex-1 relative">
                  <GlassInput
                    ref={inputRef}
                    type="text"
                    placeholder="Digite sua mensagem..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    className="pr-12"
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/60 transition-colors"
                  >
                    <Smile className="w-5 h-5" />
                  </button>
                </div>
                <GlassButton type="submit" className="px-4 py-3" disabled={!newMessage.trim()}>
                  <Send className="w-5 h-5" />
                </GlassButton>
              </form>

              {/* Typing hint */}
              <p className="text-white/30 text-xs mt-2 text-center">
                Ctrl+/ para respostas rápidas • Enter para enviar
              </p>
            </div>
          </>
        ) : (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center text-white/50">
            <div className="w-24 h-24 rounded-full bg-white/10 flex items-center justify-center mb-4">
              <MessageSquare className="w-12 h-12" />
            </div>
            <h3 className="text-xl font-medium text-white mb-2">Nenhuma conversa selecionada</h3>
            <p>Selecione uma conversa para começar a conversar</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Inbox;
