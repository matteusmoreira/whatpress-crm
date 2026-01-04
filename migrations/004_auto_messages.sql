-- =====================================================
-- WhatsApp CRM - Auto Messages Migration
-- Mensagens automáticas: boas-vindas, fora do horário, palavras-chave
-- =====================================================

-- Tabela de configurações de mensagens automáticas
CREATE TABLE IF NOT EXISTS auto_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL, -- 'welcome', 'away', 'keyword'
    name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    trigger_keyword VARCHAR(100), -- Para tipo 'keyword'
    is_active BOOLEAN DEFAULT true,
    schedule_start TIME, -- Para tipo 'away'
    schedule_end TIME, -- Para tipo 'away'
    schedule_days INTEGER[], -- 0-6, onde 0 = domingo
    delay_seconds INTEGER DEFAULT 0, -- Delay antes de enviar
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_auto_messages_tenant ON auto_messages(tenant_id);
CREATE INDEX IF NOT EXISTS idx_auto_messages_type ON auto_messages(type);
CREATE INDEX IF NOT EXISTS idx_auto_messages_keyword ON auto_messages(trigger_keyword);

-- RLS
ALTER TABLE auto_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access auto_messages" ON auto_messages FOR ALL USING (true) WITH CHECK (true);

-- Log de mensagens automáticas enviadas
CREATE TABLE IF NOT EXISTS auto_message_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    auto_message_id UUID NOT NULL REFERENCES auto_messages(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auto_message_logs_conversation ON auto_message_logs(conversation_id);

-- RLS
ALTER TABLE auto_message_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access auto_message_logs" ON auto_message_logs FOR ALL USING (true) WITH CHECK (true);

-- Dados iniciais de exemplo
-- (Será inserido via API quando o tenant configurar)
