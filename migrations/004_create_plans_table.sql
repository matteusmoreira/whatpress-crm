-- =====================================================
-- WhatsApp CRM - Migration: Create Plans Table
-- Execute este SQL no Supabase SQL Editor
-- =====================================================

-- Criar tabela de planos
CREATE TABLE IF NOT EXISTS plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    price DECIMAL(10,2) DEFAULT 0,
    max_instances INTEGER DEFAULT 1,
    max_messages_month INTEGER DEFAULT 1000,
    max_users INTEGER DEFAULT 1,
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Adicionar plan_id aos tenants (se não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tenants' AND column_name = 'plan_id'
    ) THEN
        ALTER TABLE tenants ADD COLUMN plan_id UUID REFERENCES plans(id);
    END IF;
END $$;

-- Habilitar RLS para planos
ALTER TABLE plans ENABLE ROW LEVEL SECURITY;

-- Policy de acesso total para service_role
CREATE POLICY "Service role full access plans" ON plans FOR ALL USING (true) WITH CHECK (true);

-- Inserir planos padrão
INSERT INTO plans (name, slug, price, max_instances, max_messages_month, max_users, features) VALUES
('Free', 'free', 0, 1, 500, 2, '{"automations": false, "kb": true}'),
('Starter', 'starter', 49.90, 2, 5000, 5, '{"automations": true, "kb": true}'),
('Pro', 'pro', 149.90, 5, 20000, 15, '{"automations": true, "kb": true, "api": true}'),
('Enterprise', 'enterprise', 399.90, 0, 0, 0, '{"automations": true, "kb": true, "api": true, "whitelabel": true}')
ON CONFLICT (slug) DO NOTHING;

-- Atualizar tenants existentes para usar o plano correto baseado no campo 'plan' antigo
UPDATE tenants t
SET plan_id = p.id
FROM plans p
WHERE t.plan = p.slug AND t.plan_id IS NULL;

-- Índices
CREATE INDEX IF NOT EXISTS idx_plans_slug ON plans(slug);
CREATE INDEX IF NOT EXISTS idx_plans_active ON plans(is_active);
CREATE INDEX IF NOT EXISTS idx_tenants_plan_id ON tenants(plan_id);

-- Verificar
SELECT 'Plans Created:' as table_name, count(*) as count FROM plans;
