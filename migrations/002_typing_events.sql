-- =====================================================
-- WhatsApp CRM - Typing Events Migration
-- Tabela temporária para eventos de digitação (realtime)
-- =====================================================

CREATE TABLE IF NOT EXISTS typing_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    phone VARCHAR(50) NOT NULL,
    is_typing BOOLEAN DEFAULT false,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_typing_conversation ON typing_events(conversation_id);

-- RLS
ALTER TABLE typing_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access typing" ON typing_events FOR ALL USING (true) WITH CHECK (true);

-- Limpar eventos antigos automaticamente (opcional - trigger)
CREATE OR REPLACE FUNCTION cleanup_old_typing_events()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM typing_events WHERE timestamp < NOW() - INTERVAL '30 seconds';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para limpar eventos antigos
DROP TRIGGER IF EXISTS trigger_cleanup_typing ON typing_events;
CREATE TRIGGER trigger_cleanup_typing
    AFTER INSERT ON typing_events
    FOR EACH STATEMENT
    EXECUTE FUNCTION cleanup_old_typing_events();
