-- =====================================================
-- WhatsApp CRM - Labels Migration
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- Criar tabela de labels por tenant
CREATE TABLE IF NOT EXISTS labels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    color VARCHAR(7) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Índice para busca por tenant
CREATE INDEX IF NOT EXISTS idx_labels_tenant ON labels(tenant_id);

-- Adicionar coluna labels à tabela conversations (array de UUIDs)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversations' AND column_name = 'labels'
    ) THEN
        ALTER TABLE conversations ADD COLUMN labels UUID[] DEFAULT '{}';
    END IF;
END $$;

-- RLS para labels
ALTER TABLE labels ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access labels" ON labels FOR ALL USING (true) WITH CHECK (true);

-- Dados iniciais (labels padrão para tenants existentes)
DO $$
DECLARE
    t_id UUID;
BEGIN
    FOR t_id IN SELECT id FROM tenants
    LOOP
        INSERT INTO labels (tenant_id, name, color) VALUES
        (t_id, 'Urgente', '#EF4444'),
        (t_id, 'VIP', '#F59E0B'),
        (t_id, 'Novo Cliente', '#10B981'),
        (t_id, 'Follow-up', '#3B82F6'),
        (t_id, 'Reclamação', '#DC2626'),
        (t_id, 'Venda', '#8B5CF6'),
        (t_id, 'Suporte', '#06B6D4'),
        (t_id, 'Dúvida', '#6366F1')
        ON CONFLICT (tenant_id, name) DO NOTHING;
    END LOOP;
END $$;

-- Verificar migração
SELECT 'Labels table created' as status, count(*) as labels_count FROM labels;
