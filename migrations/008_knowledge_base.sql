-- =====================================================
-- WhatsApp CRM - Knowledge Base Migration
-- Base de conhecimento e FAQ integrado
-- =====================================================

-- Tabela de categorias da base de conhecimento
CREATE TABLE IF NOT EXISTS kb_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    color VARCHAR(20),
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, slug)
);

-- Tabela de artigos do FAQ/Knowledge Base
CREATE TABLE IF NOT EXISTS kb_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    category_id UUID REFERENCES kb_categories(id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    excerpt TEXT, -- Resumo para preview
    keywords TEXT[] DEFAULT '{}', -- Para busca
    views INTEGER DEFAULT 0,
    helpful_yes INTEGER DEFAULT 0,
    helpful_no INTEGER DEFAULT 0,
    is_published BOOLEAN DEFAULT false,
    is_featured BOOLEAN DEFAULT false, -- Destaque na home
    author_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(tenant_id, slug)
);

-- Tabela de FAQs rápidas (perguntas frequentes)
CREATE TABLE IF NOT EXISTS kb_faqs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    question VARCHAR(500) NOT NULL,
    answer TEXT NOT NULL,
    category_id UUID REFERENCES kb_categories(id) ON DELETE SET NULL,
    keywords TEXT[] DEFAULT '{}',
    display_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    usage_count INTEGER DEFAULT 0, -- Quantas vezes foi usada como resposta
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Logs de busca (para analytics e melhorias)
CREATE TABLE IF NOT EXISTS kb_search_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    query VARCHAR(500) NOT NULL,
    results_count INTEGER DEFAULT 0,
    selected_article_id UUID REFERENCES kb_articles(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_kb_categories_tenant ON kb_categories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_kb_articles_tenant ON kb_articles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_kb_articles_category ON kb_articles(category_id);
CREATE INDEX IF NOT EXISTS idx_kb_articles_keywords ON kb_articles USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_kb_articles_published ON kb_articles(is_published, tenant_id);
CREATE INDEX IF NOT EXISTS idx_kb_faqs_tenant ON kb_faqs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_kb_faqs_keywords ON kb_faqs USING GIN(keywords);
CREATE INDEX IF NOT EXISTS idx_kb_search_tenant ON kb_search_logs(tenant_id);

-- Full-text search index para artigos
CREATE INDEX IF NOT EXISTS idx_kb_articles_fts ON kb_articles 
USING GIN(to_tsvector('portuguese', coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(excerpt, '')));

-- RLS
ALTER TABLE kb_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_search_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access kb_categories" ON kb_categories FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access kb_articles" ON kb_articles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access kb_faqs" ON kb_faqs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access kb_search_logs" ON kb_search_logs FOR ALL USING (true) WITH CHECK (true);
