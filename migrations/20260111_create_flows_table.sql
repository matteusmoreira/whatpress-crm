-- Create flows table for automation flow builder
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main flows table
CREATE TABLE IF NOT EXISTS flows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
    edges JSONB NOT NULL DEFAULT '[]'::jsonb,
    variables JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'paused', 'archived')),
    is_active BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_flows_tenant ON flows(tenant_id);
CREATE INDEX IF NOT EXISTS idx_flows_status ON flows(status);
CREATE INDEX IF NOT EXISTS idx_flows_active ON flows(is_active);
CREATE INDEX IF NOT EXISTS idx_flows_created_by ON flows(created_by);

-- Enable RLS
ALTER TABLE flows ENABLE ROW LEVEL SECURITY;

-- RLS Policy for service role
DROP POLICY IF EXISTS "Service role has full access to flows" ON flows;
CREATE POLICY "Service role has full access to flows" 
ON flows FOR ALL 
USING (true);

-- Create flow_executions table to track flow runs
CREATE TABLE IF NOT EXISTS flow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    flow_id UUID NOT NULL REFERENCES flows(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'paused')),
    current_node_id VARCHAR(255),
    context JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for flow_executions
CREATE INDEX IF NOT EXISTS idx_flow_executions_flow ON flow_executions(flow_id);
CREATE INDEX IF NOT EXISTS idx_flow_executions_tenant ON flow_executions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_flow_executions_conversation ON flow_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_flow_executions_status ON flow_executions(status);

-- Enable RLS
ALTER TABLE flow_executions ENABLE ROW LEVEL SECURITY;

-- RLS Policy for service role
DROP POLICY IF EXISTS "Service role has full access to flow_executions" ON flow_executions;
CREATE POLICY "Service role has full access to flow_executions" 
ON flow_executions FOR ALL 
USING (true);

-- Create flow_logs table for detailed execution tracking
CREATE TABLE IF NOT EXISTS flow_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES flow_executions(id) ON DELETE CASCADE,
    node_id VARCHAR(255) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'success' CHECK (status IN ('success', 'error', 'skipped')),
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for flow_logs
CREATE INDEX IF NOT EXISTS idx_flow_logs_execution ON flow_logs(execution_id);
CREATE INDEX IF NOT EXISTS idx_flow_logs_executed_at ON flow_logs(executed_at DESC);

-- Enable RLS
ALTER TABLE flow_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy for service role
DROP POLICY IF EXISTS "Service role has full access to flow_logs" ON flow_logs;
CREATE POLICY "Service role has full access to flow_logs" 
ON flow_logs FOR ALL 
USING (true);

-- Create updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to flows table
DROP TRIGGER IF EXISTS update_flows_updated_at ON flows;
CREATE TRIGGER update_flows_updated_at
    BEFORE UPDATE ON flows
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
