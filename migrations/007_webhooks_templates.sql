-- =====================================================
-- WhatsApp CRM - Webhooks and Templates Migration
-- Webhooks customizáveis e templates de mensagem
-- =====================================================

-- Tabela de webhooks customizáveis
CREATE TABLE IF NOT EXISTS custom_webhooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(255), -- Para validação HMAC
    events TEXT[] DEFAULT '{}', -- ['message.received', 'message.sent', 'conversation.created', etc]
    headers JSONB DEFAULT '{}', -- Headers customizados
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    last_status INTEGER, -- Último status HTTP retornado
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de templates de mensagem
CREATE TABLE IF NOT EXISTS message_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'marketing', 'support', 'sales', 'general'
    content TEXT NOT NULL,
    variables JSONB DEFAULT '[]', -- [{name: 'nome', placeholder: '{{nome}}'}]
    media_url VARCHAR(500), -- URL de mídia anexa
    media_type VARCHAR(50), -- 'image', 'video', 'document'
    usage_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Logs de disparo de webhooks
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    webhook_id UUID NOT NULL REFERENCES custom_webhooks(id) ON DELETE CASCADE,
    event VARCHAR(100) NOT NULL,
    payload JSONB,
    response_status INTEGER,
    response_body TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de contatos (para campanhas futuras)
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    email VARCHAR(255),
    tags TEXT[] DEFAULT '{}',
    custom_fields JSONB DEFAULT '{}',
    source VARCHAR(50), -- 'whatsapp', 'import', 'manual'
    last_message_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, phone)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_webhooks_tenant ON custom_webhooks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_webhooks_events ON custom_webhooks USING GIN(events);
CREATE INDEX IF NOT EXISTS idx_templates_tenant ON message_templates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_templates_category ON message_templates(category);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_webhook ON webhook_logs(webhook_id);
CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_contacts_tags ON contacts USING GIN(tags);

-- RLS
ALTER TABLE custom_webhooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access webhooks" ON custom_webhooks FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access templates" ON message_templates FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access webhook_logs" ON webhook_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access contacts" ON contacts FOR ALL USING (true) WITH CHECK (true);

-- Limpar logs antigos (manter 7 dias)
CREATE OR REPLACE FUNCTION cleanup_old_webhook_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM webhook_logs WHERE created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;
