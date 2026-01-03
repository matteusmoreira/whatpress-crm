// Domain Types for WhatsApp CRM

/**
 * @typedef {Object} Tenant
 * @property {string} id
 * @property {string} name
 * @property {string} slug
 * @property {string} status - 'active' | 'inactive' | 'suspended'
 * @property {string} plan - 'free' | 'starter' | 'pro' | 'enterprise'
 * @property {number} messagesThisMonth
 * @property {number} connectionsCount
 * @property {string} createdAt
 * @property {string} updatedAt
 */

/**
 * @typedef {Object} User
 * @property {string} id
 * @property {string} email
 * @property {string} name
 * @property {string} role - 'superadmin' | 'admin' | 'agent'
 * @property {string|null} tenantId
 * @property {string} avatar
 * @property {string} createdAt
 */

/**
 * @typedef {Object} Connection
 * @property {string} id
 * @property {string} tenantId
 * @property {string} provider - 'evolution' | 'wuzapi' | 'pastorini'
 * @property {string} instanceName
 * @property {string} phoneNumber
 * @property {string} status - 'connected' | 'disconnected' | 'connecting'
 * @property {string} webhookUrl
 * @property {Object} config
 * @property {string} createdAt
 */

/**
 * @typedef {Object} Conversation
 * @property {string} id
 * @property {string} tenantId
 * @property {string} connectionId
 * @property {string} contactPhone
 * @property {string} contactName
 * @property {string} contactAvatar
 * @property {string} status - 'open' | 'pending' | 'resolved'
 * @property {string} assignedTo
 * @property {string} lastMessageAt
 * @property {number} unreadCount
 * @property {string} lastMessagePreview
 * @property {string} createdAt
 */

/**
 * @typedef {Object} Message
 * @property {string} id
 * @property {string} conversationId
 * @property {string} content
 * @property {string} type - 'text' | 'image' | 'audio' | 'video' | 'document'
 * @property {string} direction - 'inbound' | 'outbound'
 * @property {string} status - 'sent' | 'delivered' | 'read' | 'failed'
 * @property {string|null} mediaUrl
 * @property {string} timestamp
 */

export const USER_ROLES = {
  SUPERADMIN: 'superadmin',
  ADMIN: 'admin',
  AGENT: 'agent'
};

export const CONNECTION_PROVIDERS = {
  EVOLUTION: 'evolution',
  WUZAPI: 'wuzapi',
  PASTORINI: 'pastorini'
};

export const MESSAGE_STATUS = {
  SENT: 'sent',
  DELIVERED: 'delivered',
  READ: 'read',
  FAILED: 'failed'
};

export const CONVERSATION_STATUS = {
  OPEN: 'open',
  PENDING: 'pending',
  RESOLVED: 'resolved'
};

export const TENANT_STATUS = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  SUSPENDED: 'suspended'
};
