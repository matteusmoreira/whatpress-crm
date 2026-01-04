-- =====================================================
-- WhatsApp CRM - Supabase Database Setup
-- Execute este SQL no Supabase SQL Editor
-- https://supabase.com/dashboard/project/snaqzbibxafbqxlxusdi/sql
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABELAS
-- =====================================================

-- Tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    plan VARCHAR(50) DEFAULT 'free',
    messages_this_month INTEGER DEFAULT 0,
    connections_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'agent',
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    avatar VARCHAR(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Connections table
CREATE TABLE IF NOT EXISTS connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    instance_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'disconnected',
    webhook_url VARCHAR(512),
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    connection_id UUID NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    contact_phone VARCHAR(50) NOT NULL,
    contact_name VARCHAR(255) NOT NULL,
    contact_avatar VARCHAR(512),
    status VARCHAR(50) DEFAULT 'open',
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    unread_count INTEGER DEFAULT 0,
    last_message_preview TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    type VARCHAR(50) DEFAULT 'text',
    direction VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'sent',
    media_url VARCHAR(512),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_connections_tenant ON connections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_connection ON conversations(connection_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_last_message ON conversations(last_message_at DESC);

-- =====================================================
-- ROW LEVEL SECURITY (Disable for now - service role bypasses)
-- =====================================================

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Policies for service_role (full access)
CREATE POLICY "Service role full access tenants" ON tenants FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access users" ON users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access connections" ON connections FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access conversations" ON conversations FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access messages" ON messages FOR ALL USING (true) WITH CHECK (true);

-- =====================================================
-- DADOS INICIAIS (SEED)
-- =====================================================

-- Insert tenants
INSERT INTO tenants (name, slug, status, plan, messages_this_month, connections_count) VALUES
('Minha Empresa', 'minha-empresa', 'active', 'pro', 1247, 3),
('Empresa Demo 1', 'empresa-demo-1', 'active', 'starter', 456, 1),
('Empresa Demo 2', 'empresa-demo-2', 'inactive', 'free', 89, 0)
ON CONFLICT (slug) DO NOTHING;

-- Get tenant IDs for references
DO $$
DECLARE
    tenant_1_id UUID;
    tenant_2_id UUID;
    admin_user_id UUID;
    agent_user_id UUID;
    conn_1_id UUID;
    conn_2_id UUID;
    conv_1_id UUID;
    conv_2_id UUID;
    conv_3_id UUID;
    conv_5_id UUID;
BEGIN
    SELECT id INTO tenant_1_id FROM tenants WHERE slug = 'minha-empresa';
    SELECT id INTO tenant_2_id FROM tenants WHERE slug = 'empresa-demo-1';
    
    -- Insert users (password: 123456)
    INSERT INTO users (email, password_hash, name, role, tenant_id, avatar) VALUES
    ('super@admin.com', '123456', 'Super Administrador', 'superadmin', NULL, 'https://api.dicebear.com/7.x/avataaars/svg?seed=super'),
    ('admin@minhaempresa.com', '123456', 'Carlos Silva', 'admin', tenant_1_id, 'https://api.dicebear.com/7.x/avataaars/svg?seed=carlos'),
    ('maria@minhaempresa.com', '123456', 'Maria Oliveira', 'agent', tenant_1_id, 'https://api.dicebear.com/7.x/avataaars/svg?seed=maria')
    ON CONFLICT (email) DO NOTHING;
    
    SELECT id INTO admin_user_id FROM users WHERE email = 'admin@minhaempresa.com';
    SELECT id INTO agent_user_id FROM users WHERE email = 'maria@minhaempresa.com';
    
    -- Insert connections
    INSERT INTO connections (tenant_id, provider, instance_name, phone_number, status, webhook_url, config) VALUES
    (tenant_1_id, 'evolution', 'principal-whatsapp', '+55 21 99999-8888', 'connected', 'https://api.minhaempresa.com/webhooks/evolution', '{"api_key": "evo_****_abc123"}'),
    (tenant_1_id, 'wuzapi', 'suporte-whatsapp', '+55 21 98888-7777', 'connected', 'https://api.minhaempresa.com/webhooks/wuzapi', '{"token": "wuz_****_def456"}'),
    (tenant_1_id, 'pastorini', 'vendas-whatsapp', '+55 21 97777-6666', 'disconnected', '', '{}'),
    (tenant_2_id, 'evolution', 'demo-whatsapp', '+55 11 99999-0000', 'connected', 'https://api.demo1.com/webhooks', '{"api_key": "evo_****_ghi789"}')
    ON CONFLICT DO NOTHING;
    
    SELECT id INTO conn_1_id FROM connections WHERE instance_name = 'principal-whatsapp';
    SELECT id INTO conn_2_id FROM connections WHERE instance_name = 'suporte-whatsapp';
    
    -- Insert conversations
    INSERT INTO conversations (tenant_id, connection_id, contact_phone, contact_name, contact_avatar, status, assigned_to, unread_count, last_message_preview) VALUES
    (tenant_1_id, conn_1_id, '+55 21 91234-5678', 'João Pedro', 'https://api.dicebear.com/7.x/avataaars/svg?seed=joao', 'open', agent_user_id, 3, 'Olá, preciso de ajuda com meu pedido'),
    (tenant_1_id, conn_1_id, '+55 21 98765-4321', 'Ana Beatriz', 'https://api.dicebear.com/7.x/avataaars/svg?seed=ana', 'open', agent_user_id, 0, 'Perfeito, muito obrigada!'),
    (tenant_1_id, conn_2_id, '+55 21 95555-1234', 'Roberto Costa', 'https://api.dicebear.com/7.x/avataaars/svg?seed=roberto', 'pending', NULL, 5, 'Vocês trabalham com entrega?'),
    (tenant_1_id, conn_1_id, '+55 21 94444-9876', 'Fernanda Lima', 'https://api.dicebear.com/7.x/avataaars/svg?seed=fernanda', 'resolved', admin_user_id, 0, 'Problema resolvido, até mais!'),
    (tenant_1_id, conn_2_id, '+55 21 93333-5555', 'Lucas Mendes', 'https://api.dicebear.com/7.x/avataaars/svg?seed=lucas', 'open', agent_user_id, 1, 'Qual o prazo de entrega?')
    ON CONFLICT DO NOTHING;
    
    SELECT id INTO conv_1_id FROM conversations WHERE contact_name = 'João Pedro';
    SELECT id INTO conv_2_id FROM conversations WHERE contact_name = 'Ana Beatriz';
    SELECT id INTO conv_3_id FROM conversations WHERE contact_name = 'Roberto Costa';
    SELECT id INTO conv_5_id FROM conversations WHERE contact_name = 'Lucas Mendes';
    
    -- Insert messages
    IF conv_1_id IS NOT NULL THEN
        INSERT INTO messages (conversation_id, content, type, direction, status) VALUES
        (conv_1_id, 'Olá! Boa tarde, tudo bem?', 'text', 'inbound', 'read'),
        (conv_1_id, 'Boa tarde! Tudo ótimo, como posso ajudar?', 'text', 'outbound', 'read'),
        (conv_1_id, 'Fiz um pedido semana passada e ainda não recebi', 'text', 'inbound', 'read'),
        (conv_1_id, 'Pode me informar o número do pedido, por favor?', 'text', 'outbound', 'read'),
        (conv_1_id, 'Claro! É o pedido #12345', 'text', 'inbound', 'read'),
        (conv_1_id, 'Olá, preciso de ajuda com meu pedido', 'text', 'inbound', 'delivered');
    END IF;
    
    IF conv_2_id IS NOT NULL THEN
        INSERT INTO messages (conversation_id, content, type, direction, status) VALUES
        (conv_2_id, 'Oi! Quero saber sobre os produtos', 'text', 'inbound', 'read'),
        (conv_2_id, 'Olá Ana! Claro, temos várias opções. O que você procura?', 'text', 'outbound', 'read'),
        (conv_2_id, 'Preciso de algo para presente de aniversário', 'text', 'inbound', 'read'),
        (conv_2_id, 'Temos kits especiais! Vou enviar o catálogo', 'text', 'outbound', 'read'),
        (conv_2_id, 'Perfeito, muito obrigada!', 'text', 'inbound', 'read');
    END IF;
    
    IF conv_3_id IS NOT NULL THEN
        INSERT INTO messages (conversation_id, content, type, direction, status) VALUES
        (conv_3_id, 'Boa tarde!', 'text', 'inbound', 'delivered'),
        (conv_3_id, 'Vocês trabalham com entrega?', 'text', 'inbound', 'delivered');
    END IF;
    
    IF conv_5_id IS NOT NULL THEN
        INSERT INTO messages (conversation_id, content, type, direction, status) VALUES
        (conv_5_id, 'E aí, blz? Vi o produto no Instagram', 'text', 'inbound', 'read'),
        (conv_5_id, 'Oi Lucas! Qual produto te interessou?', 'text', 'outbound', 'read'),
        (conv_5_id, 'Aquele kit premium azul', 'text', 'inbound', 'read'),
        (conv_5_id, 'Qual o prazo de entrega?', 'text', 'inbound', 'delivered');
    END IF;
END $$;

-- Verify setup
SELECT 'Tenants:' as table_name, count(*) as count FROM tenants
UNION ALL
SELECT 'Users:', count(*) FROM users
UNION ALL
SELECT 'Connections:', count(*) FROM connections
UNION ALL
SELECT 'Conversations:', count(*) FROM conversations
UNION ALL
SELECT 'Messages:', count(*) FROM messages;
