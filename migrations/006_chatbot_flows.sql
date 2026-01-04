-- =====================================================
-- WhatsApp CRM - Chatbot Flows Migration
-- Chatbot básico com fluxos de atendimento
-- =====================================================

-- Tabela de fluxos de chatbot
CREATE TABLE IF NOT EXISTS chatbot_flows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) NOT NULL, -- 'keyword', 'new_conversation', 'menu_option'
    trigger_value VARCHAR(255), -- Palavra-chave ou opção de menu
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0, -- Maior = maior prioridade
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de passos do fluxo
CREATE TABLE IF NOT EXISTS chatbot_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flow_id UUID NOT NULL REFERENCES chatbot_flows(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_type VARCHAR(50) NOT NULL, -- 'message', 'menu', 'wait_input', 'transfer', 'condition'
    message TEXT, -- Mensagem a enviar
    menu_options JSONB, -- [{key: "1", label: "Suporte", next_step_id: "..."}, ...]
    next_step_id UUID REFERENCES chatbot_steps(id), -- Próximo passo (se não for menu)
    transfer_to UUID REFERENCES users(id), -- Para quem transferir (se step_type = 'transfer')
    wait_timeout_seconds INTEGER DEFAULT 300, -- Timeout para espera de input
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela para sessões ativas de chatbot
CREATE TABLE IF NOT EXISTS chatbot_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    flow_id UUID NOT NULL REFERENCES chatbot_flows(id) ON DELETE CASCADE,
    current_step_id UUID REFERENCES chatbot_steps(id),
    session_data JSONB DEFAULT '{}', -- Dados coletados durante o fluxo
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'completed', 'transferred', 'timeout'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(conversation_id) -- Apenas uma sessão ativa por conversa
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_chatbot_flows_tenant ON chatbot_flows(tenant_id);
CREATE INDEX IF NOT EXISTS idx_chatbot_flows_trigger ON chatbot_flows(trigger_type, trigger_value);
CREATE INDEX IF NOT EXISTS idx_chatbot_steps_flow ON chatbot_steps(flow_id);
CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_conversation ON chatbot_sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chatbot_sessions_status ON chatbot_sessions(status);

-- RLS
ALTER TABLE chatbot_flows ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbot_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE chatbot_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access chatbot_flows" ON chatbot_flows FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access chatbot_steps" ON chatbot_steps FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access chatbot_sessions" ON chatbot_sessions FOR ALL USING (true) WITH CHECK (true);

-- Função para limpar sessões expiradas
CREATE OR REPLACE FUNCTION cleanup_expired_chatbot_sessions()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chatbot_sessions 
    SET status = 'timeout', ended_at = NOW()
    WHERE status = 'active' 
    AND last_activity < NOW() - INTERVAL '30 minutes';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
