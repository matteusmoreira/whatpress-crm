-- =====================================================
-- WhatsApp CRM - Agent Assignment Improvements
-- Adiciona status de agente e histórico de atribuições
-- =====================================================

-- Adicionar campo status aos usuários (online/offline/busy)
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'offline';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- Criar índice para busca por status
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- Criar tabela de histórico de atribuições
CREATE TABLE IF NOT EXISTS assignment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    assigned_by UUID NOT NULL REFERENCES users(id),
    action VARCHAR(20) NOT NULL, -- 'assigned', 'unassigned', 'transferred'
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_assignment_history_conversation ON assignment_history(conversation_id);
CREATE INDEX IF NOT EXISTS idx_assignment_history_agent ON assignment_history(assigned_to);

-- RLS
ALTER TABLE assignment_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access assignment_history" ON assignment_history FOR ALL USING (true) WITH CHECK (true);

-- View para estatísticas de agentes
CREATE OR REPLACE VIEW agent_stats AS
SELECT 
    u.id,
    u.name,
    u.email,
    u.status,
    u.last_seen,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'open') as open_conversations,
    COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'pending') as pending_conversations,
    COUNT(DISTINCT c.id) as total_assigned
FROM users u
LEFT JOIN conversations c ON c.assigned_to = u.id
WHERE u.role IN ('admin', 'agent')
GROUP BY u.id, u.name, u.email, u.status, u.last_seen;
