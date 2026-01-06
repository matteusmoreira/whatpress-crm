import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Search,
  Filter,
  Send,
  Paperclip,
  Smile,
  MoreVertical,
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
  Link2,
  Image,
  FileText,
  Mic,
  Video,
  Wifi,
  WifiOff,
  Reply,
  Trash2,
  Edit2,
  UserCircle,
  Phone,
  Mail,
  PenLine
} from 'lucide-react';
import { GlassCard, GlassInput, GlassButton, GlassBadge } from '../components/GlassCard';
import { useAppStore } from '../store/appStore';
import { useAuthStore } from '../store/authStore';
import { useRealtime } from '../context/RealtimeContext';
import { cn } from '../lib/utils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toast } from '../components/ui/glass-toaster';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../components/ui/tooltip';
import FileUpload from '../components/FileUpload';
import QuickRepliesPanel from '../components/QuickRepliesPanel';
import LabelsManager from '../components/LabelsManager';
import TypingIndicator, { useTypingIndicator } from '../components/TypingIndicator';
import { EmojiPicker } from '../components/EmojiPicker';
import { AgentsAPI, LabelsAPI, ConversationsAPI, ContactsAPI } from '../lib/api';

// Labels are now loaded from the database

const getInitials = (name) => {
  const safe = (name || '').trim();
  if (!safe) return '?';
  const parts = safe.split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] || '';
  const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || '';
  return (first + last).toUpperCase() || '?';
};

const URL_REGEX = /https?:\/\/[^\s<>()]+/gi;

const extractUrls = (text) => {
  if (!text) return [];
  const found = text.match(URL_REGEX);
  return Array.isArray(found) ? found : [];
};

const isWhatsappMediaUrl = (url) => {
  try {
    const u = new URL(url);
    const host = u.host.toLowerCase();
    if (!host.includes('whatsapp.net')) return false;
    return true;
  } catch {
    return false;
  }
};

const inferWhatsappMediaKind = (url) => {
  try {
    const u = new URL(url);
    const path = (u.pathname || '').toLowerCase();
    const search = u.searchParams;
    const mime = (search.get('mimeType') || search.get('mime_type') || '').toLowerCase();
    const combined = path + ' ' + mime;
    if (combined.includes('sticker') || combined.includes('webp')) return 'sticker';
    if (
      combined.includes('audio') ||
      combined.includes('ptt') ||
      combined.includes('.ogg') ||
      combined.includes('opus')
    ) return 'audio';
    if (
      combined.includes('video') ||
      combined.includes('.mp4') ||
      combined.includes('.3gp')
    ) return 'video';
    if (
      combined.includes('image') ||
      combined.includes('.jpg') ||
      combined.includes('.jpeg') ||
      combined.includes('.png') ||
      combined.includes('.gif')
    ) return 'image';
    return 'document';
  } catch {
    return 'unknown';
  }
};

const getWhatsappMediaMeta = (kind) => {
  switch (kind) {
    case 'sticker':
      return { label: '[Figurinha]', Icon: Image };
    case 'audio':
      return { label: '[Áudio]', Icon: Mic };
    case 'video':
      return { label: '[Vídeo]', Icon: Video };
    case 'image':
      return { label: '[Imagem]', Icon: Image };
    default:
      return { label: 'Mídia do WhatsApp', Icon: Image };
  }
};

const shortenUrl = (url) => {
  try {
    const u = new URL(url);
    const host = u.host.replace(/^www\./, '');
    const path = u.pathname.length > 20 ? u.pathname.slice(0, 20) + '…' : u.pathname;
    return host + (path && path !== '/' ? path : '');
  } catch {
    return url.length > 34 ? url.slice(0, 34) + '…' : url;
  }
};

const renderTextWithLinks = (text) => {
  if (!text) return null;
  const parts = text.split(URL_REGEX);
  const urls = extractUrls(text);
  if (urls.length === 0) return text;
  const nodes = [];
  for (let i = 0; i < parts.length; i++) {
    if (parts[i]) nodes.push(<React.Fragment key={`t-${i}`}>{parts[i]}</React.Fragment>);
    const url = urls[i];
    if (url) {
      nodes.push(
        <a
          key={`u-${i}`}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 break-all"
        >
          {shortenUrl(url)}
        </a>
      );
    }
  }
  return nodes;
};

const ContactAvatar = ({ src, name, sizeClassName, className }) => {
  const [failed, setFailed] = useState(false);
  const normalizedSrc = typeof src === 'string' && src.includes('api.dicebear.com') ? '' : (src || '');
  const showImage = Boolean(normalizedSrc) && !failed;

  return (
    <div
      className={cn(
        sizeClassName,
        'rounded-full overflow-hidden flex items-center justify-center bg-white/10 text-white/80 font-semibold select-none',
        className
      )}
    >
      {showImage ? (
        <img
          src={normalizedSrc}
          alt={name || 'Contato'}
          className="w-full h-full object-cover"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
        />
      ) : (
        <span className="text-sm">{getInitials(name)}</span>
      )}
    </div>
  );
};

// Component to display WhatsApp media (images/videos) inline
const WhatsAppMediaDisplay = ({
  type,
  mediaUrl,
  content,
  direction,
  onImageClick
}) => {
  const [loadError, setLoadError] = useState(false);
  const [loading, setLoading] = useState(true);

  // Check if it's a WhatsApp CDN URL that might be expired
  const isWhatsAppUrl = mediaUrl && (
    mediaUrl.includes('mmg.whatsapp.net') ||
    mediaUrl.includes('whatsapp.net')
  );

  // For image type with valid mediaUrl
  if (type === 'image' && mediaUrl && !loadError) {
    return (
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-xl">
            <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          </div>
        )}
        <button
          type="button"
          onClick={() => onImageClick?.({ open: true, url: mediaUrl, title: content || 'Imagem' })}
          className="block w-full rounded-xl overflow-hidden bg-black/20 focus:outline-none focus:ring-2 focus:ring-white/30"
          aria-label="Abrir imagem"
        >
          <img
            src={mediaUrl}
            alt={content || 'Imagem'}
            className={cn(
              'w-full h-auto max-h-80 object-cover transition-opacity',
              loading ? 'opacity-0' : 'opacity-100'
            )}
            loading="lazy"
            referrerPolicy="no-referrer"
            onLoad={() => setLoading(false)}
            onError={() => {
              setLoading(false);
              setLoadError(true);
            }}
          />
        </button>
      </div>
    );
  }

  // For video type with valid mediaUrl
  if (type === 'video' && mediaUrl && !loadError) {
    return (
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-xl">
            <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          </div>
        )}
        <video
          className="w-full max-h-80 rounded-xl bg-black/20"
          controls
          preload="metadata"
          playsInline
          src={mediaUrl}
          aria-label="Reprodutor de vídeo"
          onLoadedMetadata={() => setLoading(false)}
          onError={() => {
            setLoading(false);
            setLoadError(true);
          }}
        />
      </div>
    );
  }

  // For audio type with valid mediaUrl
  if (type === 'audio' && mediaUrl && !loadError) {
    return (
      <div className="relative flex items-center gap-3 p-2 rounded-xl bg-black/20 min-w-[200px]">
        <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
          <Mic className="w-5 h-5 text-emerald-400" />
        </div>
        <audio
          className="flex-1 h-8"
          controls
          preload="metadata"
          src={mediaUrl}
          aria-label="Reprodutor de áudio"
          onError={() => setLoadError(true)}
          style={{
            height: '32px',
            filter: 'invert(1) hue-rotate(180deg)',
            opacity: 0.8
          }}
        />
      </div>
    );
  }

  // Fallback for failed loads or WhatsApp URLs that expired - show clickable placeholder
  if (loadError || (isWhatsAppUrl && !mediaUrl)) {
    const mediaKind = type === 'video' ? 'video' : type === 'audio' ? 'audio' : 'image';
    const IconComponent = mediaKind === 'video' ? Video : mediaKind === 'audio' ? Mic : Image;
    const label = mediaKind === 'video' ? 'Vídeo' : mediaKind === 'audio' ? 'Áudio' : 'Imagem';

    return (
      <a
        href={mediaUrl}
        target="_blank"
        rel="noreferrer"
        className={cn(
          'flex items-center gap-3 p-3 rounded-xl border w-full',
          direction === 'outbound'
            ? 'bg-white/10 border-white/20 hover:bg-white/15'
            : 'bg-black/20 border-white/10 hover:bg-black/30'
        )}
      >
        <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
          <IconComponent className="w-5 h-5 opacity-80" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{label}</p>
          <p className="text-xs opacity-70 truncate">Clique para abrir</p>
        </div>
      </a>
    );
  }

  return null;
};

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
    updateConversationStatus,
    deleteConversation,
    clearConversationMessages,
    deleteMessage
  } = useAppStore();

  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [newMessage, setNewMessage] = useState('');
  const [selectedConnectionFilter, setSelectedConnectionFilter] = useState('all');
  const [selectedAgentFilter, setSelectedAgentFilter] = useState('all');
  const [showFileUpload, setShowFileUpload] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(false);
  const [showLabelsMenu, setShowLabelsMenu] = useState(false);
  const [showAssignMenu, setShowAssignMenu] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showLabelsManager, setShowLabelsManager] = useState(false);
  const [agents, setAgents] = useState([]);
  const [labels, setLabels] = useState([]);
  const [selectedLabelFilter, setSelectedLabelFilter] = useState('all');
  const [replyToMessage, setReplyToMessage] = useState(null);
  const [mediaViewer, setMediaViewer] = useState({ open: false, url: '', title: '' });
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [editingContactName, setEditingContactName] = useState(false);
  const [contactNameValue, setContactNameValue] = useState('');
  const [contactData, setContactData] = useState(null);
  const [useSignature, setUseSignature] = useState(user?.signatureEnabled ?? true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const tenantId = user?.tenantId || 'tenant-1';

  // Typing indicator hook
  const { setTyping, getTypingContact } = useTypingIndicator();

  // Load agents for assignment
  const loadAgents = useCallback(async () => {
    try {
      const data = await AgentsAPI.list(tenantId);
      setAgents(data);
    } catch (error) {
      console.error('Error loading agents:', error);
    }
  }, [tenantId]);

  // Load labels from database
  const loadLabels = useCallback(async () => {
    try {
      const data = await LabelsAPI.list(tenantId);
      setLabels(data);
    } catch (error) {
      console.error('Error loading labels:', error);
    }
  }, [tenantId]);

  // Fetch initial data
  useEffect(() => {
    fetchConversations(tenantId);
    fetchConnections(tenantId);
    loadAgents();
    loadLabels();
  }, [tenantId, fetchConversations, fetchConnections, loadAgents, loadLabels]);

  // Handle URL search parameter to initiate conversation
  useEffect(() => {
    const searchParam = searchParams.get('search');
    if (!searchParam || conversationsLoading) return;

    const phone = decodeURIComponent(searchParam).replace(/\D/g, ''); // Simple cleanup
    if (!phone) return;

    // Check if conversation already exists
    const existing = conversations.find(c =>
      c.contactPhone?.includes(phone) ||
      c.contactPhone?.replace(/\D/g, '') === phone
    );

    if (existing) {
      setSelectedConversation(existing.id);
      setSearchQuery(phone);
      // Clear param to avoid re-triggering
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('search');
      setSearchParams(newParams);
    } else {
      // Create new conversation
      const initiate = async () => {
        try {
          const newConv = await ConversationsAPI.initiate(phone);
          // Refresh conversations to include the new one (or optimize by adding to store directly if possible)
          // For now, re-fetching or simulating addition:
          await fetchConversations(tenantId);
          setSelectedConversation(newConv.id);
          setSearchQuery(phone);

          const newParams = new URLSearchParams(searchParams);
          newParams.delete('search');
          setSearchParams(newParams);
        } catch (error) {
          console.error("Error initiating conversation:", error);
          toast.error("Erro ao iniciar conversa");
        }
      };

      initiate();
    }
  }, [searchParams, conversations, conversationsLoading, tenantId, fetchConversations, setSelectedConversation, setSearchParams]);

  // Fallback: polling para atualizar conversas/mensagens quando realtime falhar
  useEffect(() => {
    if (!tenantId) return;
    if (realtimeConnected) return;

    const pollConversations = () => {
      if (typeof document !== 'undefined' && document.hidden) return;
      fetchConversations(tenantId, {}, { silent: true });
    };

    const pollMessages = () => {
      if (!selectedConversation?.id) return;
      if (typeof document !== 'undefined' && document.hidden) return;
      const state = useAppStore.getState();
      const currentMessages = state.messages || [];
      const last = currentMessages[currentMessages.length - 1];
      const lastTs = last?.timestamp;
      if (!lastTs) {
        state.fetchMessages(selectedConversation.id, { silent: true, tail: true, limit: 50 });
        return;
      }
      state.fetchMessages(selectedConversation.id, { silent: true, after: lastTs, append: true, limit: 200 });
    };

    pollConversations();
    pollMessages();

    const conversationsInterval = setInterval(pollConversations, 10000);
    const messagesInterval = setInterval(pollMessages, 4000);

    return () => {
      clearInterval(conversationsInterval);
      clearInterval(messagesInterval);
    };
  }, [tenantId, selectedConversation?.id, fetchConversations, realtimeConnected]);

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
        setShowMoreMenu(false);
      }
      if (e.key === '/' && e.ctrlKey) {
        e.preventDefault();
        setShowQuickReplies(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Agent heartbeat - keep online status
  useEffect(() => {
    const sendHeartbeat = async () => {
      try {
        await AgentsAPI.heartbeat();
      } catch (error) {
        console.error('Heartbeat error:', error);
      }
    };

    // Send heartbeat on mount and every 30 seconds
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 30000);

    // Set offline on unmount
    return () => {
      clearInterval(interval);
      AgentsAPI.setOffline().catch(() => { });
    };
  }, []);

  const filteredConversations = conversations.filter(conv => {
    const matchesSearch = conv.contactName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      conv.contactPhone.includes(searchQuery);
    const matchesStatus = conversationFilter === 'all' || conv.status === conversationFilter;
    const matchesConnection = selectedConnectionFilter === 'all' || conv.connectionId === selectedConnectionFilter;
    const matchesLabel = selectedLabelFilter === 'all' || (conv.labels || []).includes(selectedLabelFilter);
    const matchesAgent = selectedAgentFilter === 'all' ||
      (selectedAgentFilter === 'mine' && conv.assignedTo === user?.id) ||
      conv.assignedTo === selectedAgentFilter;
    return matchesSearch && matchesStatus && matchesConnection && matchesLabel && matchesAgent;
  });

  // Helper to get label info by ID
  const getLabelById = (labelId) => labels.find(l => l.id === labelId);

  // Helper to get agent status color
  const getAgentStatusColor = (status) => {
    switch (status) {
      case 'online': return 'bg-emerald-500';
      case 'busy': return 'bg-amber-500';
      default: return 'bg-gray-400';
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();
    if (!newMessage.trim() || !selectedConversation) return;

    try {
      // Build message with signature if enabled
      let messageToSend = newMessage.trim();

      if (useSignature && user?.name) {
        // Build signature based on user settings
        const parts = [user.name];
        if (user.signatureIncludeTitle && user.jobTitle) {
          parts.push(user.jobTitle);
        }
        if (user.signatureIncludeDepartment && user.department) {
          parts.push(user.department);
        }

        // Format: *Name* (Title / Department)\nMessage
        const signatureLine = parts.length > 1
          ? `*${parts[0]}* (${parts.slice(1).join(' / ')})`
          : `*${parts[0]}*`;

        messageToSend = `${signatureLine}\n${newMessage.trim()}`;
      }

      // TODO: Include replyToMessage.id when sending to support quoted replies
      await sendMessage(selectedConversation.id, messageToSend);
      setNewMessage('');
      setReplyToMessage(null);
      inputRef.current?.focus();
    } catch (error) {
      toast.error('Erro ao enviar mensagem');
    }
  };

  const handleFileUpload = async (fileData) => {
    // FileUpload component now handles the upload via UploadAPI
    // Just close the panel and refresh messages
    setShowFileUpload(false);
    // Messages will be updated via realtime or we can fetch manually
    if (selectedConversation?.id) {
      useAppStore.getState().fetchMessages(selectedConversation.id);
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
      // Check if label already exists on conversation
      const currentLabels = selectedConversation?.labels || [];
      if (currentLabels.includes(labelId)) {
        toast.info('Label já adicionada');
        setShowLabelsMenu(false);
        return;
      }

      await ConversationsAPI.addLabel(selectedConversation.id, labelId);

      // Update local state
      const updatedConv = {
        ...selectedConversation,
        labels: [...currentLabels, labelId]
      };
      setSelectedConversation(updatedConv);

      // Refresh conversations to get updated data
      fetchConversations(tenantId);

      toast.success('Label adicionada');
      setShowLabelsMenu(false);
    } catch (error) {
      toast.error('Erro ao adicionar label');
    }
  };

  // Handle contact editing
  const handleContactNameClick = () => {
    if (!selectedConversation) return;
    setContactNameValue(selectedConversation.contactName || '');
    setEditingContactName(true);
  };

  const handleContactNameSave = async () => {
    if (!selectedConversation || !contactNameValue.trim()) {
      toast.error('Digite um nome válido');
      return;
    }

    try {
      // First get or create the contact
      const contact = await ContactsAPI.getByPhone(tenantId, selectedConversation.contactPhone);

      // Update contact name
      await ContactsAPI.update(contact.id, { full_name: contactNameValue.trim() });

      // Update local state
      const updatedConv = { ...selectedConversation, contactName: contactNameValue.trim() };
      setSelectedConversation(updatedConv);

      // Refresh conversations
      fetchConversations(tenantId);

      toast.success('Nome atualizado');
      setEditingContactName(false);
    } catch (error) {
      toast.error('Erro ao atualizar nome');
    }
  };

  const handleViewContact = async () => {
    if (!selectedConversation) return;

    try {
      const contact = await ContactsAPI.getByPhone(tenantId, selectedConversation.contactPhone);
      setContactData(contact);
      setShowContactModal(true);
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao carregar contato');
    }
  };

  const handleEmojiSelect = (emoji) => {
    setNewMessage(prev => prev + emoji);
    setShowEmojiPicker(false);
    inputRef.current?.focus();
  };

  const handleDeleteConversation = async () => {
    if (!selectedConversation?.id) return;
    const ok = window.confirm('Deseja excluir esta conversa? Isso também remove as mensagens.');
    if (!ok) return;
    try {
      await deleteConversation(selectedConversation.id);
      toast.success('Conversa excluída');
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao excluir conversa');
    }
  };

  const handleClearMessages = async () => {
    if (!selectedConversation?.id) return;
    const ok = window.confirm('Deseja excluir todas as mensagens desta conversa?');
    if (!ok) return;
    try {
      await clearConversationMessages(selectedConversation.id);
      toast.success('Mensagens excluídas');
      setShowMoreMenu(false);
    } catch (error) {
      toast.error('Erro ao excluir mensagens');
    }
  };

  const handleDeleteMessage = async (messageId) => {
    if (!messageId) return;
    const ok = window.confirm('Deseja excluir esta mensagem?');
    if (!ok) return;
    try {
      await deleteMessage(messageId);
      toast.success('Mensagem excluída');
    } catch (error) {
      toast.error('Erro ao excluir mensagem');
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

  const getMessageOriginInfo = (msg) => {
    const rawOrigin = msg.origin || (msg.direction === 'inbound' ? 'customer' : 'agent');
    const origin = String(rawOrigin || '').toLowerCase();
    if (origin === 'system') {
      return {
        label: 'Sistema',
        badgeClass: 'bg-purple-500/10 border-purple-400 text-purple-200',
        dotClass: 'bg-purple-400',
        tooltip: 'Mensagem automática enviada pelo sistema'
      };
    }
    if (origin === 'customer') {
      return {
        label: 'Cliente',
        badgeClass: 'bg-emerald-500/10 border-emerald-400 text-emerald-200',
        dotClass: 'bg-emerald-400',
        tooltip: 'Mensagem enviada pelo cliente'
      };
    }
    return {
      label: 'Agente',
      badgeClass: 'bg-sky-500/10 border-sky-400 text-sky-200',
      dotClass: 'bg-sky-400',
      tooltip: 'Mensagem enviada por um agente humano'
    };
  };

  const formatTime = (timestamp) => {
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ptBR });
    } catch {
      return '';
    }
  };

  return (
    <div className="h-full min-h-0 flex flex-col lg:flex-row">
      {/* Conversations List */}
      <div className="w-full lg:w-96 min-h-0 border-r border-white/10 flex flex-col bg-black/20">
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
        <div className="p-3 border-b border-white/10 flex gap-2">
          <select
            value={selectedConnectionFilter}
            onChange={(e) => setSelectedConnectionFilter(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas conexões</option>
            {connections.map(conn => (
              <option key={conn.id} value={conn.id} className="bg-emerald-900">
                {conn.phoneNumber}
              </option>
            ))}
          </select>
          <select
            value={selectedLabelFilter}
            onChange={(e) => setSelectedLabelFilter(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todas labels</option>
            {labels.map(label => (
              <option key={label.id} value={label.id} className="bg-emerald-900">
                {label.name}
              </option>
            ))}
          </select>
        </div>

        {/* Agent filter */}
        <div className="p-3 border-b border-white/10">
          <select
            value={selectedAgentFilter}
            onChange={(e) => setSelectedAgentFilter(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all" className="bg-emerald-900">Todos os agentes</option>
            <option value="mine" className="bg-emerald-900">Minhas conversas</option>
            <option value="" className="bg-emerald-900">Não atribuídas</option>
            {agents.map(agent => (
              <option key={agent.id} value={agent.id} className="bg-emerald-900">
                {agent.name} {agent.status === 'online' ? '🟢' : '⚫'}
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
                    <ContactAvatar
                      src={conv.contactAvatar}
                      name={conv.contactName}
                      sizeClassName="w-12 h-12"
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
                    <div className="flex items-center gap-1 mt-1">
                      <span className="text-white/30 text-xs">{conv.contactPhone}</span>
                      {/* Labels badges */}
                      {(conv.labels || []).slice(0, 2).map(labelId => {
                        const label = getLabelById(labelId);
                        if (!label) return null;
                        return (
                          <span
                            key={labelId}
                            className="text-xs px-1.5 py-0.5 rounded-full text-white/90"
                            style={{ backgroundColor: label.color + '40' }}
                          >
                            {label.name}
                          </span>
                        );
                      })}
                      {(conv.labels || []).length > 2 && (
                        <span className="text-xs text-white/40">+{conv.labels.length - 2}</span>
                      )}
                    </div>
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

      <TooltipProvider>
        {/* Chat Area */}
        <div className="flex-1 min-h-0 flex flex-col bg-gradient-to-br from-emerald-950/50 to-teal-950/50">
          {selectedConversation ? (
            <>
              {/* Chat Header */}
              <div className="p-4 border-b border-white/10 backdrop-blur-sm bg-black/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <ContactAvatar
                      src={selectedConversation.contactAvatar}
                      name={selectedConversation.contactName}
                      sizeClassName="w-10 h-10"
                    />
                    <div>
                      {editingContactName ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={contactNameValue}
                            onChange={(e) => setContactNameValue(e.target.value)}
                            className="px-2 py-1 bg-white/10 border border-white/20 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleContactNameSave();
                              if (e.key === 'Escape') setEditingContactName(false);
                            }}
                          />
                          <button
                            onClick={handleContactNameSave}
                            className="p-1 bg-emerald-500 rounded text-white hover:bg-emerald-600"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingContactName(false)}
                            className="p-1 bg-white/10 rounded text-white/60 hover:bg-white/20"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <h2 className="text-white font-medium">{selectedConversation.contactName}</h2>
                      )}
                      <button
                        onClick={handleContactNameClick}
                        className="text-white/50 text-sm hover:text-emerald-400 hover:underline transition-colors flex items-center gap-1"
                        title="Clique para editar nome do contato"
                      >
                        {selectedConversation.contactPhone}
                        <Edit2 className="w-3 h-3 opacity-0 group-hover:opacity-100" />
                      </button>
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
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <p className="text-white/50 text-xs px-2 mb-2">Atribuir para:</p>
                            {/* Sort agents: online first */}
                            {[...agents]
                              .sort((a, b) => (a.status === 'online' ? -1 : 1) - (b.status === 'online' ? -1 : 1))
                              .map(agent => (
                                <button
                                  key={agent.id}
                                  onClick={() => handleAssign(agent.id)}
                                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                                >
                                  <div className="relative">
                                    <img src={agent.avatar} alt={agent.name} className="w-6 h-6 rounded-full" />
                                    <span
                                      className={cn(
                                        'absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-emerald-900',
                                        getAgentStatusColor(agent.status)
                                      )}
                                    />
                                  </div>
                                  <span className="flex-1 text-left">{agent.name}</span>
                                  <span className="text-xs text-white/40 capitalize">{agent.status || 'offline'}</span>
                                </button>
                              ))}
                            {/* Unassign option */}
                            {selectedConversation?.assignedTo && (
                              <button
                                onClick={async () => {
                                  try {
                                    await ConversationsAPI.unassign(selectedConversation.id);
                                    toast.success('Conversa desatribuída');
                                    setShowAssignMenu(false);
                                  } catch (error) {
                                    toast.error('Erro ao desatribuir');
                                  }
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-500/20 text-red-400 text-sm mt-2 border-t border-white/10 pt-2"
                              >
                                <X className="w-4 h-4" />
                                Remover atribuição
                              </button>
                            )}
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
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <p className="text-white/50 text-xs px-2 mb-2">Adicionar label:</p>
                            {labels.map(label => (
                              <button
                                key={label.id}
                                onClick={() => handleAddLabel(label.id)}
                                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                              >
                                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: label.color }} />
                                {label.name}
                              </button>
                            ))}
                            <div className="border-t border-white/10 mt-2 pt-2">
                              <button
                                onClick={() => {
                                  setShowLabelsMenu(false);
                                  setShowLabelsManager(true);
                                }}
                                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/70 hover:text-white text-sm"
                              >
                                <Tag className="w-4 h-4" />
                                Gerenciar Labels
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="relative">
                      <button
                        onClick={() => {
                          setShowMoreMenu(!showMoreMenu);
                          setShowAssignMenu(false);
                          setShowLabelsMenu(false);
                        }}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                        title="Mais opções"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      {showMoreMenu && (
                        <div className="absolute right-0 top-full mt-2 w-56 backdrop-blur-xl bg-emerald-900/95 border border-white/20 rounded-xl shadow-xl z-50">
                          <div className="p-2">
                            <button
                              onClick={handleViewContact}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <UserCircle className="w-4 h-4" />
                              Ver contato
                            </button>
                            <button
                              onClick={handleClearMessages}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 text-white text-sm"
                            >
                              <Trash2 className="w-4 h-4" />
                              Excluir mensagens
                            </button>
                            <button
                              onClick={handleDeleteConversation}
                              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-red-500/20 text-red-400 text-sm mt-1"
                            >
                              <Trash2 className="w-4 h-4" />
                              Excluir conversa
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-4">
                {messagesLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <>
                    {messages.map((msg) => (
                      <div key={msg.id}>
                        {(() => {
                          const rawContent = typeof msg.content === 'string'
                            ? msg.content
                            : msg.content == null
                              ? ''
                              : String(msg.content);
                          const hasContent = rawContent.trim().length > 0;
                          const fallback =
                            msg.type === 'audio' ? '[Áudio]' :
                              msg.type === 'image' ? '[Imagem]' :
                                msg.type === 'video' ? '[Vídeo]' :
                                  msg.type === 'document' ? '[Documento]' :
                                    '[Mensagem]';
                          const displayContent = hasContent ? rawContent : fallback;
                          const mediaUrl = typeof msg.mediaUrl === 'string' && msg.mediaUrl.trim() ? msg.mediaUrl.trim() : '';
                          const isMediaType = ['image', 'video', 'audio', 'document'].includes(msg.type);
                          const canInlineMedia = Boolean(mediaUrl) && isMediaType;
                          const urls = extractUrls(displayContent);
                          const hasOnlyUrl = msg.type === 'text' && urls.length === 1 && displayContent.trim() === urls[0];
                          const primaryUrl = hasOnlyUrl ? urls[0] : '';
                          const isWhatsappMedia = primaryUrl ? isWhatsappMediaUrl(primaryUrl) : false;

                          // Check if the content contains a WhatsApp media URL (for image/video types)
                          const contentUrls = extractUrls(rawContent);
                          const contentWhatsappUrl = contentUrls.find(u => isWhatsappMediaUrl(u)) || '';
                          const hasWhatsappMediaInContent = Boolean(contentWhatsappUrl);

                          // Use mediaUrl if available, otherwise try to extract from content for media types
                          const effectiveMediaUrl = mediaUrl || (isMediaType && contentWhatsappUrl ? contentWhatsappUrl : '');
                          const shouldRenderMedia = Boolean(effectiveMediaUrl) && isMediaType;

                          const mediaKind = isWhatsappMedia ? inferWhatsappMediaKind(primaryUrl) :
                            (hasWhatsappMediaInContent ? inferWhatsappMediaKind(contentWhatsappUrl) : 'unknown');
                          const whatsappMeta = isWhatsappMedia ? getWhatsappMediaMeta(mediaKind) : null;
                          const originInfo = getMessageOriginInfo(msg);

                          return (
                            <div
                              className={cn(
                                'flex group',
                                msg.direction === 'outbound' ? 'justify-end' : 'justify-start'
                              )}
                            >
                              {msg.direction === 'outbound' && (
                                <div className="self-center mr-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                                  <button
                                    onClick={() => handleDeleteMessage(msg.id)}
                                    className="p-1.5 rounded-full hover:bg-red-500/20 text-white/40 hover:text-red-300 transition-all"
                                    title="Excluir"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                  <button
                                    onClick={() => { setReplyToMessage(msg); inputRef.current?.focus(); }}
                                    className="p-1.5 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition-all"
                                    title="Responder"
                                  >
                                    <Reply className="w-4 h-4" />
                                  </button>
                                </div>
                              )}

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
                                {/* Render media inline using WhatsAppMediaDisplay */}
                                {shouldRenderMedia && (msg.type === 'image' || msg.type === 'video' || msg.type === 'audio') && (
                                  <WhatsAppMediaDisplay
                                    type={msg.type}
                                    mediaUrl={effectiveMediaUrl}
                                    content={displayContent}
                                    direction={msg.direction}
                                    onImageClick={setMediaViewer}
                                  />
                                )}
                                {shouldRenderMedia && msg.type === 'document' && (
                                  <a
                                    href={effectiveMediaUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className={cn(
                                      'flex items-center gap-3 p-3 rounded-xl border w-full',
                                      msg.direction === 'outbound'
                                        ? 'bg-white/10 border-white/20 hover:bg-white/15'
                                        : 'bg-black/20 border-white/10 hover:bg-black/30'
                                    )}
                                  >
                                    <FileText className="w-5 h-5 opacity-80" />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium truncate">{displayContent || 'Documento'}</p>
                                      <p className="text-xs opacity-70 truncate">{shortenUrl(effectiveMediaUrl)}</p>
                                    </div>
                                  </a>
                                )}
                                {/* WhatsApp media URL in text message - render inline */}
                                {msg.type === 'text' && hasOnlyUrl && isWhatsappMedia && (
                                  <WhatsAppMediaDisplay
                                    type={mediaKind === 'video' ? 'video' : mediaKind === 'audio' ? 'audio' : 'image'}
                                    mediaUrl={primaryUrl}
                                    content={whatsappMeta?.label || 'Mídia do WhatsApp'}
                                    direction={msg.direction}
                                    onImageClick={setMediaViewer}
                                  />
                                )}
                                {msg.type === 'text' && hasOnlyUrl && !isWhatsappMedia && (
                                  <a
                                    href={primaryUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className={cn(
                                      'flex items-center gap-3 p-3 rounded-xl border w-full',
                                      msg.direction === 'outbound'
                                        ? 'bg-white/10 border-white/20 hover:bg-white/15'
                                        : 'bg-black/20 border-white/10 hover:bg-black/30'
                                    )}
                                  >
                                    <div className="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center">
                                      <Link2 className="w-5 h-5 opacity-80" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium truncate">{shortenUrl(primaryUrl)}</p>
                                      <p className="text-xs opacity-70 truncate">{primaryUrl}</p>
                                    </div>
                                  </a>
                                )}
                                {(!shouldRenderMedia && !(msg.type === 'text' && hasOnlyUrl)) && (
                                  <p className={cn('whitespace-pre-wrap', !hasContent && 'italic text-white/70')}>
                                    {renderTextWithLinks(displayContent)}
                                  </p>
                                )}
                                {shouldRenderMedia && hasContent && msg.type !== 'document' && (
                                  <p className="whitespace-pre-wrap mt-2">
                                    {renderTextWithLinks(rawContent)}
                                  </p>
                                )}
                                <div
                                  className={cn(
                                    'flex items-center justify-between gap-2 mt-1',
                                    msg.direction === 'outbound' ? 'text-white/70' : 'text-white/40'
                                  )}
                                >
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <div
                                        className={cn(
                                          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] uppercase tracking-wide',
                                          originInfo.badgeClass
                                        )}
                                      >
                                        <span
                                          className={cn(
                                            'w-1.5 h-1.5 rounded-full',
                                            originInfo.dotClass
                                          )}
                                        />
                                        <span>{originInfo.label}</span>
                                      </div>
                                    </TooltipTrigger>
                                    <TooltipContent side="top" sideOffset={6}>
                                      {originInfo.tooltip}
                                    </TooltipContent>
                                  </Tooltip>
                                  <div className="flex items-center gap-1">
                                    <span className="text-xs">
                                      {new Date(msg.timestamp).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    {msg.direction === 'outbound' && getStatusIcon(msg.status)}
                                  </div>
                                </div>
                              </div>

                              {msg.direction === 'inbound' && (
                                <div className="self-center ml-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                                  <button
                                    onClick={() => handleDeleteMessage(msg.id)}
                                    className="p-1.5 rounded-full hover:bg-red-500/20 text-white/40 hover:text-red-300 transition-all"
                                    title="Excluir"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                  </button>
                                  <button
                                    onClick={() => { setReplyToMessage(msg); inputRef.current?.focus(); }}
                                    className="p-1.5 rounded-full hover:bg-white/10 text-white/40 hover:text-white transition-all"
                                    title="Responder"
                                  >
                                    <Reply className="w-4 h-4" />
                                  </button>
                                </div>
                              )}
                            </div>
                          );
                        })()}
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
                    conversationId={selectedConversation?.id}
                    onUpload={handleFileUpload}
                    onCancel={() => setShowFileUpload(false)}
                  />
                </div>
              )}

              {/* Typing Indicator */}
              {selectedConversation && getTypingContact(selectedConversation.id) && (
                <div className="px-4 pb-2">
                  <TypingIndicator
                    contactName={getTypingContact(selectedConversation.id)}
                  />
                </div>
              )}

              {/* Reply Preview */}
              {replyToMessage && (
                <div className="px-4 pt-2 border-t border-white/10">
                  <div className="flex items-start gap-3 p-3 bg-white/5 rounded-lg border-l-2 border-emerald-500">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Reply className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400 text-xs font-medium">
                          Respondendo a {replyToMessage.direction === 'inbound' ? selectedConversation?.contactName : 'você'}
                        </span>
                      </div>
                      <p className="text-white/60 text-sm truncate">
                        {(typeof replyToMessage.content === 'string' && replyToMessage.content.trim().length > 0)
                          ? replyToMessage.content
                          : '[Mensagem]'}
                      </p>
                    </div>
                    <button
                      onClick={() => setReplyToMessage(null)}
                      className="p-1 hover:bg-white/10 rounded text-white/40 hover:text-white"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
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
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        onClick={() => setUseSignature(!useSignature)}
                        className={cn(
                          'p-2 rounded-lg transition-colors',
                          useSignature
                            ? 'bg-emerald-500 text-white'
                            : 'hover:bg-white/10 text-white/60 hover:text-white'
                        )}
                        title={useSignature ? 'Assinatura ativada' : 'Assinatura desativada'}
                      >
                        <PenLine className="w-5 h-5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {useSignature ? 'Desativar assinatura' : 'Ativar assinatura'}
                    </TooltipContent>
                  </Tooltip>
                  <div className="flex-1 relative">
                    <GlassInput
                      ref={inputRef}
                      type="text"
                      placeholder="Digite sua mensagem..."
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      className="pr-12"
                    />
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <button
                        type="button"
                        onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                        className={cn(
                          "text-white/40 hover:text-white/60 transition-colors",
                          showEmojiPicker && "text-emerald-400"
                        )}
                      >
                        <Smile className="w-5 h-5" />
                      </button>
                      {showEmojiPicker && (
                        <EmojiPicker
                          onSelect={handleEmojiSelect}
                          onClose={() => setShowEmojiPicker(false)}
                          position="top"
                        />
                      )}
                    </div>
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
      </TooltipProvider>

      <Dialog open={mediaViewer.open} onOpenChange={(open) => setMediaViewer(prev => ({ ...prev, open }))}>
        <DialogContent className="max-w-4xl bg-black/80 border border-white/10 p-3">
          <img
            src={mediaViewer.url}
            alt={mediaViewer.title || 'Imagem'}
            className="w-full h-auto max-h-[80vh] object-contain rounded-lg"
            referrerPolicy="no-referrer"
          />
        </DialogContent>
      </Dialog>

      {/* Contact View Modal */}
      <Dialog open={showContactModal} onOpenChange={setShowContactModal}>
        <DialogContent className="max-w-md bg-gradient-to-br from-emerald-900/95 to-teal-900/95 backdrop-blur-xl border border-white/20">
          <div className="p-6">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <Users className="w-5 h-5 text-emerald-400" />
              Informações do Contato
            </h2>

            {contactData ? (
              <div className="space-y-4">
                {/* Avatar and Name */}
                <div className="flex items-center gap-4">
                  <ContactAvatar
                    src={null}
                    name={contactData.fullName}
                    sizeClassName="w-16 h-16"
                  />
                  <div>
                    <h3 className="text-lg font-semibold text-white">{contactData.fullName}</h3>
                    <p className="text-white/60 text-sm">{contactData.phone}</p>
                  </div>
                </div>

                {/* Contact Details */}
                <div className="space-y-3 mt-6">
                  {/* Phone */}
                  <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                    <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                      <Phone className="w-4 h-4 text-emerald-400" />
                    </div>
                    <div>
                      <p className="text-white/50 text-xs">Telefone</p>
                      <p className="text-white">{contactData.phone}</p>
                    </div>
                  </div>

                  {/* Email */}
                  {contactData.email && (
                    <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                        <Mail className="w-4 h-4 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-white/50 text-xs">Email</p>
                        <p className="text-white">{contactData.email}</p>
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {contactData.tags && contactData.tags.length > 0 && (
                    <div className="p-3 bg-white/5 rounded-lg">
                      <p className="text-white/50 text-xs mb-2">Tags</p>
                      <div className="flex flex-wrap gap-2">
                        {contactData.tags.map((tag, idx) => (
                          <span key={idx} className="px-2 py-1 bg-emerald-500/20 text-emerald-300 text-xs rounded-full">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Custom Fields */}
                  {contactData.customFields && Object.keys(contactData.customFields).length > 0 && (
                    <div className="p-3 bg-white/5 rounded-lg">
                      <p className="text-white/50 text-xs mb-2">Campos Personalizados</p>
                      <div className="space-y-2">
                        {Object.entries(contactData.customFields).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-white/60 text-sm capitalize">{key.replace(/_/g, ' ')}</span>
                            <span className="text-white text-sm">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Source */}
                  {contactData.source && (
                    <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                      <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                        <FileText className="w-4 h-4 text-purple-400" />
                      </div>
                      <div>
                        <p className="text-white/50 text-xs">Origem</p>
                        <p className="text-white capitalize">{contactData.source}</p>
                      </div>
                    </div>
                  )}

                  {/* Created At */}
                  {contactData.createdAt && (
                    <div className="text-center text-white/40 text-xs mt-4">
                      Criado em {new Date(contactData.createdAt).toLocaleDateString('pt-BR')}
                    </div>
                  )}
                </div>

                {/* Close Button */}
                <div className="mt-6 flex justify-end">
                  <GlassButton onClick={() => setShowContactModal(false)}>
                    Fechar
                  </GlassButton>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center p-8">
                <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Labels Manager Modal */}
      <LabelsManager
        isOpen={showLabelsManager}
        onClose={() => setShowLabelsManager(false)}
        onLabelsChange={loadLabels}
      />
    </div>
  );
};

export default Inbox;
