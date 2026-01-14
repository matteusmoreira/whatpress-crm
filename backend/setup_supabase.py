"""
Script para criar as tabelas no Supabase
Execute com: python setup_supabase.py
"""

from supabase_client import supabase
import json
from passlib.context import CryptContext

_PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

def setup_database():
    """Cria as tabelas necessárias no Supabase usando SQL"""
    
    sql_commands = """
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Tenants table
    CREATE TABLE IF NOT EXISTS tenants (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
        plan VARCHAR(50) DEFAULT 'free' CHECK (plan IN ('free', 'starter', 'pro', 'enterprise')),
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
        role VARCHAR(50) DEFAULT 'agent' CHECK (role IN ('superadmin', 'admin', 'agent')),
        tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
        avatar VARCHAR(512),
        job_title VARCHAR(120),
        department VARCHAR(120),
        signature_enabled BOOLEAN DEFAULT true,
        signature_include_title BOOLEAN DEFAULT false,
        signature_include_department BOOLEAN DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Connections table
    CREATE TABLE IF NOT EXISTS connections (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        provider VARCHAR(50) NOT NULL CHECK (provider IN ('evolution', 'wuzapi', 'pastorini')),
        instance_name VARCHAR(255) NOT NULL,
        phone_number VARCHAR(50) NOT NULL,
        status VARCHAR(50) DEFAULT 'disconnected' CHECK (status IN ('connected', 'disconnected', 'connecting')),
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
        status VARCHAR(50) DEFAULT 'open' CHECK (status IN ('open', 'pending', 'resolved')),
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
        type VARCHAR(50) DEFAULT 'text' CHECK (type IN ('text', 'image', 'audio', 'video', 'document', 'sticker', 'system')),
        direction VARCHAR(50) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
        status VARCHAR(50) DEFAULT 'sent' CHECK (status IN ('sent', 'delivered', 'read', 'failed')),
        media_url TEXT,
        external_id VARCHAR(255),
        metadata JSONB DEFAULT '{}'::jsonb,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Contacts table
    CREATE TABLE IF NOT EXISTS contacts (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name VARCHAR(255),
        full_name VARCHAR(255),
        phone VARCHAR(50) NOT NULL,
        email VARCHAR(255),
        tags JSONB DEFAULT '[]',
        custom_fields JSONB DEFAULT '{}',
        social_links JSONB DEFAULT '{}',
        notes_html TEXT DEFAULT '',
        source VARCHAR(50) DEFAULT 'manual',
        status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'unverified', 'verified')),
        first_contact_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_tenant_phone_unique ON contacts(tenant_id, phone);
    CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);

    -- Auto messages table
    CREATE TABLE IF NOT EXISTS auto_messages (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        type VARCHAR(50) NOT NULL CHECK (type IN ('welcome', 'away', 'keyword')),
        name VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        trigger_keyword VARCHAR(255),
        is_active BOOLEAN DEFAULT true,
        schedule_start VARCHAR(10),
        schedule_end VARCHAR(10),
        schedule_days JSONB,
        delay_seconds INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Auto message logs (avoid duplicates / track sends)
    CREATE TABLE IF NOT EXISTS auto_message_logs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
        auto_message_id UUID NOT NULL REFERENCES auto_messages(id) ON DELETE CASCADE,
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_connections_tenant ON connections(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_connection ON conversations(connection_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_conversations_last_message ON conversations(last_message_at DESC);
    CREATE INDEX IF NOT EXISTS idx_auto_messages_tenant ON auto_messages(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_auto_messages_active ON auto_messages(is_active);
    CREATE INDEX IF NOT EXISTS idx_auto_message_logs_auto_message ON auto_message_logs(auto_message_id);
    CREATE INDEX IF NOT EXISTS idx_auto_message_logs_conversation ON auto_message_logs(conversation_id);

    -- Enable Row Level Security
    ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
    ALTER TABLE users ENABLE ROW LEVEL SECURITY;
    ALTER TABLE connections ENABLE ROW LEVEL SECURITY;
    ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
    ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
    ALTER TABLE auto_messages ENABLE ROW LEVEL SECURITY;
    ALTER TABLE auto_message_logs ENABLE ROW LEVEL SECURITY;

    -- Create policies for service role (bypass RLS)
    CREATE POLICY IF NOT EXISTS "Service role has full access to tenants" ON tenants FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to users" ON users FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to connections" ON connections FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to conversations" ON conversations FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to messages" ON messages FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to contacts" ON contacts FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to auto_messages" ON auto_messages FOR ALL USING (true);
    CREATE POLICY IF NOT EXISTS "Service role has full access to auto_message_logs" ON auto_message_logs FOR ALL USING (true);
    """
    
    # Execute SQL via Supabase REST API
    try:
        result = supabase.rpc('exec_sql', {'sql': sql_commands}).execute()
        print("Database setup completed!")
        return True
    except Exception as e:
        print(f"Note: Direct SQL execution might not be available. Error: {e}")
        print("Please run the SQL commands manually in the Supabase SQL Editor.")
        return False


def seed_data():
    """Insere dados iniciais"""
    
    # Check if data already exists
    existing_tenants = supabase.table('tenants').select('id').limit(1).execute()
    if existing_tenants.data:
        print("Data already exists, skipping seed...")
        return
    
    print("Seeding database...")
    
    # Insert tenants
    tenants_data = [
        {
            'name': 'Minha Empresa',
            'slug': 'minha-empresa',
            'status': 'active',
            'plan': 'pro',
            'messages_this_month': 1247,
            'connections_count': 3
        },
        {
            'name': 'Empresa Demo 1',
            'slug': 'empresa-demo-1',
            'status': 'active',
            'plan': 'starter',
            'messages_this_month': 456,
            'connections_count': 1
        },
        {
            'name': 'Empresa Demo 2',
            'slug': 'empresa-demo-2',
            'status': 'inactive',
            'plan': 'free',
            'messages_this_month': 89,
            'connections_count': 0
        }
    ]
    
    tenants_result = supabase.table('tenants').insert(tenants_data).execute()
    tenants = tenants_result.data
    print(f"Created {len(tenants)} tenants")
    
    tenant_1_id = tenants[0]['id']
    tenant_2_id = tenants[1]['id']
    
    # Insert users (password: 123456 - in production use proper hashing)
    demo_password_hash = _PASSWORD_CONTEXT.hash("123456")
    users_data = [
        {
            'email': 'super@admin.com',
            'password_hash': demo_password_hash,
            'name': 'Super Administrador',
            'role': 'superadmin',
            'tenant_id': None,
            'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=super'
        },
        {
            'email': 'admin@minhaempresa.com',
            'password_hash': demo_password_hash,
            'name': 'Carlos Silva',
            'role': 'admin',
            'tenant_id': tenant_1_id,
            'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=carlos'
        },
        {
            'email': 'maria@minhaempresa.com',
            'password_hash': demo_password_hash,
            'name': 'Maria Oliveira',
            'role': 'agent',
            'tenant_id': tenant_1_id,
            'avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=maria'
        }
    ]
    
    users_result = supabase.table('users').insert(users_data).execute()
    users = users_result.data
    print(f"Created {len(users)} users")
    
    admin_user_id = users[1]['id']
    agent_user_id = users[2]['id']
    
    # Insert connections
    connections_data = [
        {
            'tenant_id': tenant_1_id,
            'provider': 'evolution',
            'instance_name': 'principal-whatsapp',
            'phone_number': '+55 21 99999-8888',
            'status': 'connected',
            'webhook_url': 'https://api.minhaempresa.com/webhooks/evolution',
            'config': {'api_key': 'evo_****_abc123'}
        },
        {
            'tenant_id': tenant_1_id,
            'provider': 'wuzapi',
            'instance_name': 'suporte-whatsapp',
            'phone_number': '+55 21 98888-7777',
            'status': 'connected',
            'webhook_url': 'https://api.minhaempresa.com/webhooks/wuzapi',
            'config': {'token': 'wuz_****_def456'}
        },
        {
            'tenant_id': tenant_1_id,
            'provider': 'pastorini',
            'instance_name': 'vendas-whatsapp',
            'phone_number': '+55 21 97777-6666',
            'status': 'disconnected',
            'webhook_url': '',
            'config': {}
        },
        {
            'tenant_id': tenant_2_id,
            'provider': 'evolution',
            'instance_name': 'demo-whatsapp',
            'phone_number': '+55 11 99999-0000',
            'status': 'connected',
            'webhook_url': 'https://api.demo1.com/webhooks',
            'config': {'api_key': 'evo_****_ghi789'}
        }
    ]
    
    connections_result = supabase.table('connections').insert(connections_data).execute()
    connections = connections_result.data
    print(f"Created {len(connections)} connections")
    
    conn_1_id = connections[0]['id']
    conn_2_id = connections[1]['id']
    
    # Insert conversations
    conversations_data = [
        {
            'tenant_id': tenant_1_id,
            'connection_id': conn_1_id,
            'contact_phone': '+55 21 91234-5678',
            'contact_name': 'João Pedro',
            'contact_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=joao',
            'status': 'open',
            'assigned_to': agent_user_id,
            'unread_count': 3,
            'last_message_preview': 'Olá, preciso de ajuda com meu pedido'
        },
        {
            'tenant_id': tenant_1_id,
            'connection_id': conn_1_id,
            'contact_phone': '+55 21 98765-4321',
            'contact_name': 'Ana Beatriz',
            'contact_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=ana',
            'status': 'open',
            'assigned_to': agent_user_id,
            'unread_count': 0,
            'last_message_preview': 'Perfeito, muito obrigada!'
        },
        {
            'tenant_id': tenant_1_id,
            'connection_id': conn_2_id,
            'contact_phone': '+55 21 95555-1234',
            'contact_name': 'Roberto Costa',
            'contact_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=roberto',
            'status': 'pending',
            'assigned_to': None,
            'unread_count': 5,
            'last_message_preview': 'Vocês trabalham com entrega?'
        },
        {
            'tenant_id': tenant_1_id,
            'connection_id': conn_1_id,
            'contact_phone': '+55 21 94444-9876',
            'contact_name': 'Fernanda Lima',
            'contact_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=fernanda',
            'status': 'resolved',
            'assigned_to': admin_user_id,
            'unread_count': 0,
            'last_message_preview': 'Problema resolvido, até mais!'
        },
        {
            'tenant_id': tenant_1_id,
            'connection_id': conn_2_id,
            'contact_phone': '+55 21 93333-5555',
            'contact_name': 'Lucas Mendes',
            'contact_avatar': 'https://api.dicebear.com/7.x/avataaars/svg?seed=lucas',
            'status': 'open',
            'assigned_to': agent_user_id,
            'unread_count': 1,
            'last_message_preview': 'Qual o prazo de entrega?'
        }
    ]
    
    conversations_result = supabase.table('conversations').insert(conversations_data).execute()
    conversations = conversations_result.data
    print(f"Created {len(conversations)} conversations")
    
    conv_1_id = conversations[0]['id']
    conv_2_id = conversations[1]['id']
    conv_3_id = conversations[2]['id']
    conv_5_id = conversations[4]['id']
    
    # Insert messages
    messages_data = [
        # Conversation 1
        {'conversation_id': conv_1_id, 'content': 'Olá! Boa tarde, tudo bem?', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_1_id, 'content': 'Boa tarde! Tudo ótimo, como posso ajudar?', 'type': 'text', 'direction': 'outbound', 'status': 'read'},
        {'conversation_id': conv_1_id, 'content': 'Fiz um pedido semana passada e ainda não recebi', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_1_id, 'content': 'Pode me informar o número do pedido, por favor?', 'type': 'text', 'direction': 'outbound', 'status': 'read'},
        {'conversation_id': conv_1_id, 'content': 'Claro! É o pedido #12345', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_1_id, 'content': 'Olá, preciso de ajuda com meu pedido', 'type': 'text', 'direction': 'inbound', 'status': 'delivered'},
        # Conversation 2
        {'conversation_id': conv_2_id, 'content': 'Oi! Quero saber sobre os produtos', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_2_id, 'content': 'Olá Ana! Claro, temos várias opções. O que você procura?', 'type': 'text', 'direction': 'outbound', 'status': 'read'},
        {'conversation_id': conv_2_id, 'content': 'Preciso de algo para presente de aniversário', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_2_id, 'content': 'Temos kits especiais! Vou enviar o catálogo 📋', 'type': 'text', 'direction': 'outbound', 'status': 'read'},
        {'conversation_id': conv_2_id, 'content': 'Perfeito, muito obrigada!', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        # Conversation 3
        {'conversation_id': conv_3_id, 'content': 'Boa tarde!', 'type': 'text', 'direction': 'inbound', 'status': 'delivered'},
        {'conversation_id': conv_3_id, 'content': 'Vocês trabalham com entrega?', 'type': 'text', 'direction': 'inbound', 'status': 'delivered'},
        # Conversation 5
        {'conversation_id': conv_5_id, 'content': 'E aí, blz? Vi o produto no Instagram', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_5_id, 'content': 'Oi Lucas! Qual produto te interessou?', 'type': 'text', 'direction': 'outbound', 'status': 'read'},
        {'conversation_id': conv_5_id, 'content': 'Aquele kit premium azul', 'type': 'text', 'direction': 'inbound', 'status': 'read'},
        {'conversation_id': conv_5_id, 'content': 'Qual o prazo de entrega?', 'type': 'text', 'direction': 'inbound', 'status': 'delivered'},
    ]
    
    messages_result = supabase.table('messages').insert(messages_data).execute()
    print(f"Created {len(messages_result.data)} messages")
    
    print("\\n✅ Database seeded successfully!")


if __name__ == '__main__':
    seed_data()
