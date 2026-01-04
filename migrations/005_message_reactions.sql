-- =====================================================
-- WhatsApp CRM - Message Reactions Migration
-- Emoji reactions para mensagens
-- =====================================================

-- Tabela de reações a mensagens
CREATE TABLE IF NOT EXISTS message_reactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    emoji VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(message_id, user_id, emoji)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_reactions_message ON message_reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_reactions_user ON message_reactions(user_id);

-- RLS
ALTER TABLE message_reactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access reactions" ON message_reactions FOR ALL USING (true) WITH CHECK (true);
