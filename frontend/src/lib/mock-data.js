// Mock Data for WhatsApp CRM
import { USER_ROLES, CONNECTION_PROVIDERS, MESSAGE_STATUS, CONVERSATION_STATUS, TENANT_STATUS } from './types';

export const mockTenants = [
  {
    id: 'tenant-1',
    name: 'Minha Empresa',
    slug: 'minha-empresa',
    status: TENANT_STATUS.ACTIVE,
    plan: 'pro',
    messagesThisMonth: 1247,
    connectionsCount: 3,
    createdAt: '2024-01-15T10:00:00Z',
    updatedAt: '2025-07-01T14:30:00Z'
  },
  {
    id: 'tenant-2',
    name: 'Empresa Demo 1',
    slug: 'empresa-demo-1',
    status: TENANT_STATUS.ACTIVE,
    plan: 'starter',
    messagesThisMonth: 456,
    connectionsCount: 1,
    createdAt: '2024-03-20T08:00:00Z',
    updatedAt: '2025-06-28T16:45:00Z'
  },
  {
    id: 'tenant-3',
    name: 'Empresa Demo 2',
    slug: 'empresa-demo-2',
    status: TENANT_STATUS.INACTIVE,
    plan: 'free',
    messagesThisMonth: 89,
    connectionsCount: 0,
    createdAt: '2024-06-10T12:00:00Z',
    updatedAt: '2025-06-15T09:20:00Z'
  }
];

export const mockUsers = [
  {
    id: 'user-super',
    email: 'super@admin.com',
    password: '123456',
    name: 'Super Administrador',
    role: USER_ROLES.SUPERADMIN,
    tenantId: null,
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=super',
    createdAt: '2024-01-01T00:00:00Z'
  },
  {
    id: 'user-admin-1',
    email: 'admin@minhaempresa.com',
    password: '123456',
    name: 'Carlos Silva',
    role: USER_ROLES.ADMIN,
    tenantId: 'tenant-1',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=carlos',
    createdAt: '2024-01-16T10:00:00Z'
  },
  {
    id: 'user-agent-1',
    email: 'maria@minhaempresa.com',
    password: '123456',
    name: 'Maria Oliveira',
    role: USER_ROLES.AGENT,
    tenantId: 'tenant-1',
    avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=maria',
    createdAt: '2024-02-01T08:00:00Z'
  }
];

export const mockConnections = [
  {
    id: 'conn-1',
    tenantId: 'tenant-1',
    provider: CONNECTION_PROVIDERS.EVOLUTION,
    instanceName: 'principal-whatsapp',
    phoneNumber: '+55 21 99999-8888',
    status: 'connected',
    webhookUrl: 'https://api.minhaempresa.com/webhooks/evolution',
    config: { apiKey: 'evo_****_abc123' },
    createdAt: '2024-01-20T10:00:00Z'
  },
  {
    id: 'conn-2',
    tenantId: 'tenant-1',
    provider: CONNECTION_PROVIDERS.WUZAPI,
    instanceName: 'suporte-whatsapp',
    phoneNumber: '+55 21 98888-7777',
    status: 'connected',
    webhookUrl: 'https://api.minhaempresa.com/webhooks/wuzapi',
    config: { token: 'wuz_****_def456' },
    createdAt: '2024-02-15T14:00:00Z'
  },
  {
    id: 'conn-3',
    tenantId: 'tenant-1',
    provider: CONNECTION_PROVIDERS.PASTORINI,
    instanceName: 'vendas-whatsapp',
    phoneNumber: '+55 21 97777-6666',
    status: 'disconnected',
    webhookUrl: '',
    config: {},
    createdAt: '2024-03-01T09:00:00Z'
  },
  {
    id: 'conn-4',
    tenantId: 'tenant-2',
    provider: CONNECTION_PROVIDERS.EVOLUTION,
    instanceName: 'demo-whatsapp',
    phoneNumber: '+55 11 99999-0000',
    status: 'connected',
    webhookUrl: 'https://api.demo1.com/webhooks',
    config: { apiKey: 'evo_****_ghi789' },
    createdAt: '2024-03-25T11:00:00Z'
  }
];

export const mockConversations = [
  {
    id: 'conv-1',
    tenantId: 'tenant-1',
    connectionId: 'conn-1',
    contactPhone: '+55 21 91234-5678',
    contactName: 'João Pedro',
    contactAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=joao',
    status: CONVERSATION_STATUS.OPEN,
    assignedTo: 'user-agent-1',
    lastMessageAt: '2025-07-01T15:30:00Z',
    unreadCount: 3,
    lastMessagePreview: 'Olá, preciso de ajuda com meu pedido',
    createdAt: '2025-06-28T10:00:00Z'
  },
  {
    id: 'conv-2',
    tenantId: 'tenant-1',
    connectionId: 'conn-1',
    contactPhone: '+55 21 98765-4321',
    contactName: 'Ana Beatriz',
    contactAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=ana',
    status: CONVERSATION_STATUS.OPEN,
    assignedTo: 'user-agent-1',
    lastMessageAt: '2025-07-01T14:45:00Z',
    unreadCount: 0,
    lastMessagePreview: 'Perfeito, muito obrigada!',
    createdAt: '2025-06-25T08:30:00Z'
  },
  {
    id: 'conv-3',
    tenantId: 'tenant-1',
    connectionId: 'conn-2',
    contactPhone: '+55 21 95555-1234',
    contactName: 'Roberto Costa',
    contactAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=roberto',
    status: CONVERSATION_STATUS.PENDING,
    assignedTo: null,
    lastMessageAt: '2025-07-01T12:20:00Z',
    unreadCount: 5,
    lastMessagePreview: 'Vocês trabalham com entrega?',
    createdAt: '2025-07-01T12:15:00Z'
  },
  {
    id: 'conv-4',
    tenantId: 'tenant-1',
    connectionId: 'conn-1',
    contactPhone: '+55 21 94444-9876',
    contactName: 'Fernanda Lima',
    contactAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=fernanda',
    status: CONVERSATION_STATUS.RESOLVED,
    assignedTo: 'user-admin-1',
    lastMessageAt: '2025-06-30T18:00:00Z',
    unreadCount: 0,
    lastMessagePreview: 'Problema resolvido, até mais!',
    createdAt: '2025-06-20T14:00:00Z'
  },
  {
    id: 'conv-5',
    tenantId: 'tenant-1',
    connectionId: 'conn-2',
    contactPhone: '+55 21 93333-5555',
    contactName: 'Lucas Mendes',
    contactAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=lucas',
    status: CONVERSATION_STATUS.OPEN,
    assignedTo: 'user-agent-1',
    lastMessageAt: '2025-07-01T16:00:00Z',
    unreadCount: 1,
    lastMessagePreview: 'Qual o prazo de entrega?',
    createdAt: '2025-06-29T09:00:00Z'
  }
];

export const mockMessages = [
  // Conversation 1 messages
  {
    id: 'msg-1-1',
    conversationId: 'conv-1',
    content: 'Olá! Boa tarde, tudo bem?',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-28T10:00:00Z'
  },
  {
    id: 'msg-1-2',
    conversationId: 'conv-1',
    content: 'Boa tarde! Tudo ótimo, como posso ajudar?',
    type: 'text',
    direction: 'outbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-28T10:02:00Z'
  },
  {
    id: 'msg-1-3',
    conversationId: 'conv-1',
    content: 'Fiz um pedido semana passada e ainda não recebi',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-28T10:05:00Z'
  },
  {
    id: 'msg-1-4',
    conversationId: 'conv-1',
    content: 'Pode me informar o número do pedido, por favor?',
    type: 'text',
    direction: 'outbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-28T10:06:00Z'
  },
  {
    id: 'msg-1-5',
    conversationId: 'conv-1',
    content: 'Claro! É o pedido #12345',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-07-01T15:25:00Z'
  },
  {
    id: 'msg-1-6',
    conversationId: 'conv-1',
    content: 'Olá, preciso de ajuda com meu pedido',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.DELIVERED,
    mediaUrl: null,
    timestamp: '2025-07-01T15:30:00Z'
  },
  // Conversation 2 messages
  {
    id: 'msg-2-1',
    conversationId: 'conv-2',
    content: 'Oi! Quero saber sobre os produtos',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-25T08:30:00Z'
  },
  {
    id: 'msg-2-2',
    conversationId: 'conv-2',
    content: 'Olá Ana! Claro, temos várias opções. O que você procura?',
    type: 'text',
    direction: 'outbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-25T08:35:00Z'
  },
  {
    id: 'msg-2-3',
    conversationId: 'conv-2',
    content: 'Preciso de algo para presente de aniversário',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-07-01T14:40:00Z'
  },
  {
    id: 'msg-2-4',
    conversationId: 'conv-2',
    content: 'Temos kits especiais! Vou enviar o catálogo 📋',
    type: 'text',
    direction: 'outbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-07-01T14:42:00Z'
  },
  {
    id: 'msg-2-5',
    conversationId: 'conv-2',
    content: 'Perfeito, muito obrigada!',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-07-01T14:45:00Z'
  },
  // Conversation 3 messages
  {
    id: 'msg-3-1',
    conversationId: 'conv-3',
    content: 'Boa tarde!',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.DELIVERED,
    mediaUrl: null,
    timestamp: '2025-07-01T12:15:00Z'
  },
  {
    id: 'msg-3-2',
    conversationId: 'conv-3',
    content: 'Vocês trabalham com entrega?',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.DELIVERED,
    mediaUrl: null,
    timestamp: '2025-07-01T12:20:00Z'
  },
  // Conversation 5 messages
  {
    id: 'msg-5-1',
    conversationId: 'conv-5',
    content: 'E aí, blz? Vi o produto no Instagram',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-29T09:00:00Z'
  },
  {
    id: 'msg-5-2',
    conversationId: 'conv-5',
    content: 'Oi Lucas! Qual produto te interessou?',
    type: 'text',
    direction: 'outbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-06-29T09:05:00Z'
  },
  {
    id: 'msg-5-3',
    conversationId: 'conv-5',
    content: 'Aquele kit premium azul',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.READ,
    mediaUrl: null,
    timestamp: '2025-07-01T15:55:00Z'
  },
  {
    id: 'msg-5-4',
    conversationId: 'conv-5',
    content: 'Qual o prazo de entrega?',
    type: 'text',
    direction: 'inbound',
    status: MESSAGE_STATUS.DELIVERED,
    mediaUrl: null,
    timestamp: '2025-07-01T16:00:00Z'
  }
];

export const generateId = () => {
  return 'id-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
};
