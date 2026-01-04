# WhatsApp CRM - Roadmap de Desenvolvimento

> Última atualização: Janeiro 2026

## Visão Geral do Projeto

Um sistema SaaS de CRM para WhatsApp com design glassmorphism, integração com Evolution API, e funcionalidades completas de gestão de conversas e clientes.

---

## Status Atual

### ✅ Concluído

#### Fase 1 - Frontend Base
- [x] Design glassmorphism com paleta verde
- [x] Página de Login com autenticação
- [x] Dashboard de SuperAdmin
- [x] Página de Caixa de Entrada (Inbox)
- [x] Página de Conexões WhatsApp
- [x] Página de Perfil do Utilizador
- [x] Página de Configurações
- [x] Sistema de notificações (toasts)
- [x] Contadores animados
- [x] Modal de busca avançada (⌘K)
- [x] Sidebar responsivo

#### Fase 2 - Backend e Integração
- [x] Backend FastAPI
- [x] Integração com Supabase (PostgreSQL)
- [x] Sistema de autenticação JWT
- [x] API de Tenants (multi-tenancy básico)
- [x] API de Conexões
- [x] API de Conversas
- [x] API de Mensagens
- [x] API de Agentes
- [x] API de Labels/Etiquetas
- [x] API de Respostas Rápidas

#### Fase 3 - Evolution API
- [x] Integração com Evolution API v2.3.7
- [x] Listagem de instâncias
- [x] Envio de mensagens via Evolution API
- [x] Webhooks para recebimento de mensagens
- [x] Modal de QR Code para conexão

#### Funcionalidades Adicionais
- [x] Realtime com Supabase (RealtimeProvider)
- [x] Indicador "Ao vivo" de conexão
- [x] Upload de arquivos (imagens, vídeos, áudios, documentos)
- [x] Painel de Respostas Rápidas
- [x] Tema Dark/Light com toggle

---

## ✅ Concluído Recentemente

### Prioridade Alta (P0) - Implementado em Janeiro 2026

#### Melhorias de UX
- [x] **Indicador "A digitar..."** - Mostrar quando o contacto está a escrever
  - Frontend: Componente `TypingIndicator` com animação
  - Backend: Handler de webhook para eventos de presença
  - Evolution API: Evento `PRESENCE_UPDATE` configurado

#### Gestão de Conversas
- [x] **Atribuição de Agentes** - Funcionalidade completa
  - Dropdown de seleção de agente com status online
  - Heartbeat para manter status atualizado
  - Filtro por agente no inbox ("Minhas conversas", "Não atribuídas")
  - Histórico de atribuições

- [x] **Tags/Etiquetas em Conversas**
  - UI para adicionar/remover tags
  - Filtro por tags no inbox
  - Cores personalizáveis para tags (color picker)
  - LabelsManager para gerenciar tags por tenant
  - Badges de tags visíveis na lista de conversas

---

## ✅ Prioridade Média (P1) - CONCLUÍDO

### Dashboard e Relatórios (Janeiro 2026)
- [x] **Dashboard de Métricas** - Gráficos, cards, métricas em tempo real
- [x] **Relatórios Exportáveis** - Export CSV de conversas e agentes

### Funcionalidades de Chat (Janeiro 2026)
- [x] **Mensagens de Áudio** - Gravação no browser + player customizado
- [x] **Mensagens de Localização** - Picker com preview de mapa
- [x] **Reações a Mensagens** - Emoji reactions com API
- [x] **Responder Mensagem Específica** - Quote/reply com preview

### Automações (Janeiro 2026)
- [x] **Mensagens Automáticas** - Welcome, away, keyword triggers
- [x] **Chatbot Básico** - Flows, steps, menu de opções, transferência

---

## 🚧 Prioridade Baixa (P2) - EM PROGRESSO

### Funcionalidades Implementadas (Janeiro 2026)
- [x] **Webhooks Customizáveis** - CRUD + eventos configuráveis
- [x] **Templates de Mensagem** - Categorias, variáveis, uso
- [x] **Base de Conhecimento** - Artigos, FAQs, busca integrada

---

### Prioridade Baixa (P2) - Pendente

#### Multi-tenancy Completo
- [ ] **Auto-registo de Tenants**
  - Página de registo público
  - Verificação de email
  - Onboarding wizard

- [ ] **Planos e Limites**
  - Plano Free (limites básicos)
  - Plano Pro (funcionalidades avançadas)
  - Plano Enterprise (sem limites)
  - Controle de uso por plano

- [ ] **Faturação**
  - Integração com Stripe
  - Histórico de faturas
  - Upgrade/downgrade de plano

#### Integrações Adicionais
- [ ] **Outros Provedores WhatsApp**
  - Wuzapi
  - Pastorini
  - API Oficial do WhatsApp Business

- [ ] **CRM Externos**
  - Integração com HubSpot
  - Integração com Salesforce
  - Integração com Pipedrive

- [x] **Ferramentas de Produtividade**
  - Integração com Google Calendar
  - Integração com Slack
  - Webhooks customizáveis

#### Funcionalidades Avançadas
- [x] **Campanhas de Marketing**
  - Envio em massa
  - Segmentação de contactos
  - Templates de mensagem
  - Métricas de campanha

- [x] **Base de Conhecimento**
  - FAQ integrado
  - Artigos de ajuda
  - Busca inteligente

- [ ] **IA e Machine Learning**
  - Sugestão de respostas com IA
  - Análise de sentimento
  - Categorização automática de conversas
  - Resumo automático de conversas longas

---

## 🔧 Melhorias Técnicas

### Infraestrutura
- [ ] Configurar Supabase Storage bucket para uploads
- [ ] Implementar rate limiting na API
- [ ] Adicionar cache Redis para performance
- [ ] Logs estruturados com ElasticSearch
- [ ] Monitoramento com Sentry

### Segurança
- [ ] Hash de passwords com bcrypt
- [ ] Autenticação 2FA
- [ ] Audit logs
- [ ] Encriptação de dados sensíveis
- [ ] GDPR compliance

### Performance
- [ ] Paginação em todas as listas
- [ ] Lazy loading de mensagens
- [ ] Otimização de queries Supabase
- [ ] CDN para assets estáticos
- [ ] Service Worker para offline

### Qualidade de Código
- [ ] Testes unitários (Jest)
- [ ] Testes E2E (Playwright)
- [ ] CI/CD pipeline
- [ ] Documentação da API (Swagger)
- [ ] Storybook para componentes

---

## 📱 Mobile

### App Mobile (Futuro)
- [ ] React Native app
- [ ] Push notifications
- [ ] Sincronização offline
- [ ] Touch ID / Face ID

---

## 📅 Timeline Sugerida

### Q1 2026
- Indicador "A digitar..."
- Atribuição de agentes completa
- Tags em conversas
- Dashboard de métricas básico

### Q2 2026
- Mensagens de áudio
- Automações básicas
- Relatórios exportáveis
- Melhorias de segurança

### Q3 2026
- Multi-tenancy completo
- Planos e faturação
- Integrações CRM
- Campanhas básicas

### Q4 2026
- IA e sugestões
- App mobile
- Funcionalidades enterprise
- Expansão de integrações

---

## 🎯 KPIs de Sucesso

- **Uptime**: > 99.9%
- **Tempo de resposta API**: < 200ms
- **Satisfação do utilizador**: > 4.5/5
- **Retenção de clientes**: > 80%
- **Conversões Free → Pro**: > 15%

---

## 📝 Notas

### Credenciais de Teste
- **Admin**: admin@minhaempresa.com / 123456
- **SuperAdmin**: super@admin.com / 123456

### Integrações Atuais
- **Supabase**: Database e Realtime
- **Evolution API**: WhatsApp (v2.3.7)

### Stack Tecnológica
- **Frontend**: React, Tailwind CSS, shadcn/ui, Zustand
- **Backend**: FastAPI (Python)
- **Database**: Supabase (PostgreSQL)
- **Realtime**: Supabase Realtime (WebSockets)

---

*Este roadmap é um documento vivo e será atualizado conforme o progresso do desenvolvimento.*
